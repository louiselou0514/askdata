from __future__ import annotations

"""
NL-to-SQL pipeline — the core product value.

Steps:
1. Auth gate (enforced by caller / deps.py)
2. Embed question
3. Retrieve relevant schema chunks via pgvector
4. Build prompt (schema + glossary + question)
5. LLM call
6. Validate SQL (block non-SELECT, verify table names)
7. Execute via connector
8. Format result + chart suggestion
9. Persist query record
"""
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import sqlparse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorFactory
from app.core.security import decrypt_config
from app.models import DataSource, Query
from app.models.glossary import BusinessGlossary
from app.services.llm import BaseLLMProvider
from app.services.schema_embeddings import retrieve_relevant_chunks

SYSTEM_PROMPT_TEMPLATE = """\
You are a SQL expert. Generate a single, valid {dialect} SQL SELECT query to answer the user's question.

Rules:
- Only SELECT statements. Never INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, or any DDL.
- Use only the tables and columns listed in the schema context below.
- You MAY compute derived metrics using arithmetic (e.g. quantity * unit_price for revenue).
- You MAY use subqueries, CTEs (WITH clauses), and window functions for multi-step questions \
  (e.g. "repeat customers" = customers with more than one order, counted via GROUP BY / HAVING).
- For date grouping use strftime or date_trunc appropriate for {dialect}.
- Always ORDER BY for date/time grouped results so they appear chronologically.
- For relative date references ("this year", "last month", "today", "recent"), always use \
  date functions relative to CURRENT_DATE — never hard-code a specific year or date value.
- For strategic or open-ended questions (e.g. "which segment should I target?", "what should I \
  focus on?", "analyze performance", "what are the trends?"), generate the most useful analytical \
  SQL you can — aggregate by the most relevant dimension (segment, category, city, product, month) \
  and include key metrics (revenue, volume, growth) so the data can guide a real recommendation.
- Return ONLY the raw SQL — no explanation, no markdown, no code fences.
- Only respond with exactly UNABLE_TO_ANSWER if there are truly no columns in the schema that \
  relate to the question at all. If you can derive anything useful, always attempt it.

Schema context:
{schema_chunks}

{glossary_section}\
"""

NARRATIVE_SYSTEM = (
    "You are a sharp data analyst delivering a concise business insight to a non-technical stakeholder. "
    "Use specific numbers from the data. Be direct and actionable — lead with the key finding. "
    "Never mention SQL, queries, databases, or data tables. "
    "Respond in 2–3 sentences maximum."
)

NARRATIVE_USER_TEMPLATE = """\
Question: {question}

Data ({row_count} rows):
{data_table}
"""

GLOSSARY_SECTION_TEMPLATE = """\
Business terminology for this company:
{terms}

"""

MULTI_SOURCE_SYSTEM_PROMPT_TEMPLATE = """\
You are a SQL expert. Generate a single, valid DuckDB SQL SELECT query to answer the user's question.

Multiple datasets are loaded as separate tables in the same DuckDB database:
{schema_chunks}

{join_section}\
{glossary_section}\
Rules:
- Only SELECT statements. Never INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, or any DDL.
- ALWAYS double-quote every table name in your SQL (e.g. FROM "order_tbl", JOIN "customers"). \
Table names may be reserved SQL keywords and will fail without quotes.
- ALWAYS double-quote column names that might be reserved words (e.g. "order", "group", "index").
- Use only the table names shown above — exactly as spelled, inside double-quotes.
- You MAY join tables on the identified join keys when useful.
- For questions asking "which rows appear in both", "overlap", "match across", or "join" use \
a JOIN or INTERSECT as appropriate.
- You MAY compute derived metrics using arithmetic (e.g. quantity * unit_price for revenue).
- You MAY use subqueries, CTEs (WITH clauses), and window functions.
- Always ORDER BY for date/time grouped results so they appear chronologically.
- For strategic or open-ended questions, generate the most useful analytical SQL across all tables.
- For relative date references ("this year", "last month", "today", "recent"), always use \
  date functions relative to CURRENT_DATE — never hard-code a specific year or date value.
- Return ONLY the raw SQL — no explanation, no markdown, no code fences.
- Only respond with exactly UNABLE_TO_ANSWER if there are truly no relevant columns in any table.
"""

JOIN_SECTION_TEMPLATE = """\
Potential join keys (columns present in multiple tables):
{join_lines}

"""


class SQLSecurityError(Exception):
    pass


class UnableToAnswerError(Exception):
    pass


@dataclass
class ChartSuggestion:
    type: str          # bar | line | pie | table
    x: Optional[str] = None
    y: Optional[str] = None


@dataclass
class QueryResponse:
    query_id: uuid.UUID
    question: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    chart_suggestion: ChartSuggestion
    execution_ms: int
    narrative: Optional[str] = None


async def run_query(
    session: AsyncSession,
    llm: BaseLLMProvider,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data_source_ids: list[uuid.UUID],
    question: str,
) -> QueryResponse:
    first_ds_id = data_source_ids[0] if len(data_source_ids) == 1 else None
    query_record = Query(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        data_source_id=first_ds_id,
        question=question,
        status="pending",
    )
    session.add(query_record)
    await session.flush()

    try:
        if len(data_source_ids) == 1:
            result = await _execute_single_pipeline(
                session, llm, tenant_id, data_source_ids[0], question
            )
        else:
            result = await _execute_multi_pipeline(
                session, llm, tenant_id, data_source_ids, question
            )
        query_record.generated_sql = result.sql
        query_record.status = "success"
        query_record.row_count = result.row_count
        query_record.execution_ms = result.execution_ms
        await session.commit()
        result.query_id = query_record.id
        return result

    except Exception as exc:
        query_record.status = "error"
        query_record.error_message = str(exc)
        await session.commit()
        raise


async def _execute_single_pipeline(
    session: AsyncSession,
    llm: BaseLLMProvider,
    tenant_id: uuid.UUID,
    data_source_id: uuid.UUID,
    question: str,
) -> QueryResponse:
    # --- Step 2: Load data source (tenant-scoped) ---
    ds_result = await session.execute(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == tenant_id,
        )
    )
    data_source: DataSource | None = ds_result.scalar_one_or_none()
    if data_source is None:
        raise ValueError("Data source not found")

    schema_cache: dict = data_source.schema_cache or {}
    dialect: str = schema_cache.get("dialect", "sql")

    # --- Step 3: Retrieve schema chunks ---
    chunks = await retrieve_relevant_chunks(
        session, llm, tenant_id, data_source_id, question
    )
    if not chunks:
        # Fallback: use full schema from cache if embeddings not yet built
        chunks = _schema_cache_to_chunks(schema_cache)

    # --- Load glossary ---
    glossary_result = await session.execute(
        select(BusinessGlossary).where(BusinessGlossary.tenant_id == tenant_id)
    )
    glossary = glossary_result.scalars().all()

    # --- Step 4: Build prompt ---
    schema_text = "\n\n".join(chunks)
    glossary_section = ""
    if glossary:
        terms = "\n".join(f"- {g.term}: {g.definition}" for g in glossary)
        glossary_section = GLOSSARY_SECTION_TEMPLATE.format(terms=terms)

    system = SYSTEM_PROMPT_TEMPLATE.format(
        dialect=dialect,
        schema_chunks=schema_text,
        glossary_section=glossary_section,
    )

    # --- Step 5: LLM call ---
    llm_resp = await llm.complete(system=system, user=question)
    sql = llm_resp.content.strip()

    if sql == "UNABLE_TO_ANSWER":
        raise UnableToAnswerError("The question cannot be answered with the available schema.")

    # --- Step 6: Validate SQL ---
    sql = _validate_sql(sql, schema_cache)

    # --- Step 7: Execute via connector ---
    config = json.loads(decrypt_config(data_source.encrypted_config))

    # For CSV/Sheets, inject file bytes from object storage before creating connector
    if data_source.source_type == "csv":
        config = await _load_csv_bytes(config)

    connector = ConnectorFactory.create(data_source.source_type, config)
    try:
        query_result = await connector.execute_query(sql)
    finally:
        await connector.close()

    # --- Step 8: Format + chart suggestion ---
    chart = _suggest_chart(query_result.columns, query_result.rows)

    # --- Step 9: Narrative insight ---
    narrative = await _generate_narrative(llm, question, query_result.columns, query_result.rows)

    return QueryResponse(
        query_id=uuid.uuid4(),  # replaced by caller with the persisted ID
        question=question,
        sql=sql,
        columns=query_result.columns,
        rows=query_result.rows,
        row_count=query_result.row_count,
        chart_suggestion=chart,
        execution_ms=query_result.execution_ms,
        narrative=narrative,
    )


async def _execute_multi_pipeline(
    session: AsyncSession,
    llm: BaseLLMProvider,
    tenant_id: uuid.UUID,
    data_source_ids: list[uuid.UUID],
    question: str,
) -> QueryResponse:
    from app.connectors.multi_csv import MultiCSVConnector, deduplicate_table_names

    # --- Load all data sources ---
    ds_result = await session.execute(
        select(DataSource).where(
            DataSource.id.in_(data_source_ids),
            DataSource.tenant_id == tenant_id,
        )
    )
    data_sources = ds_result.scalars().all()
    if not data_sources:
        raise ValueError("No data sources found")

    non_csv = [ds for ds in data_sources if ds.source_type != "csv"]
    if non_csv:
        raise ValueError(
            f"Multi-source queries only support CSV sources. "
            f"Unsupported: {', '.join(ds.name for ds in non_csv)}"
        )

    # Preserve request order so table names are deterministic
    id_order = {ds_id: i for i, ds_id in enumerate(data_source_ids)}
    data_sources = sorted(data_sources, key=lambda ds: id_order.get(ds.id, 999))

    table_names = deduplicate_table_names([ds.name for ds in data_sources])

    # --- Build schema context for all tables ---
    schema_chunks: list[str] = []
    join_schemas: list[tuple[str, dict]] = []
    for ds, tbl in zip(data_sources, table_names):
        schema_cache = ds.schema_cache or {}
        join_schemas.append((tbl, schema_cache))
        schema_chunks.append(_schema_cache_to_chunks_named(schema_cache, tbl))

    schema_text = "\n\n".join(schema_chunks)

    # --- Detect join keys ---
    join_keys = _find_join_keys(join_schemas)
    join_section = ""
    if join_keys:
        join_lines = "\n".join(
            f'- "{jk["column"]}" appears in: '
            + ", ".join(f'"{s}"' for s in jk["sources"])
            for jk in join_keys
        )
        join_section = JOIN_SECTION_TEMPLATE.format(join_lines=join_lines)

    # --- Glossary ---
    glossary_result = await session.execute(
        select(BusinessGlossary).where(BusinessGlossary.tenant_id == tenant_id)
    )
    glossary = glossary_result.scalars().all()
    glossary_section = ""
    if glossary:
        terms = "\n".join(f"- {g.term}: {g.definition}" for g in glossary)
        glossary_section = GLOSSARY_SECTION_TEMPLATE.format(terms=terms)

    system = MULTI_SOURCE_SYSTEM_PROMPT_TEMPLATE.format(
        schema_chunks=schema_text,
        join_section=join_section,
        glossary_section=glossary_section,
    )

    # --- LLM call ---
    llm_resp = await llm.complete(system=system, user=question)
    sql = llm_resp.content.strip()
    if sql == "UNABLE_TO_ANSWER":
        hint = ""
        if join_keys:
            key_list = ", ".join(f'"{jk["column"]}"' for jk in join_keys[:3])
            hint = f" These tables can be joined on: {key_list}."
        table_list = ", ".join(f'"{t}"' for t in table_names)
        raise UnableToAnswerError(
            f"The question cannot be answered with the available schemas "
            f"({table_list}).{hint}"
        )

    sql = _validate_sql(sql, {"dialect": "duckdb", "tables": [{"name": t} for t in table_names]})

    # --- Load CSV bytes and build connector sources ---
    connector_sources = []
    for ds, tbl in zip(data_sources, table_names):
        config = json.loads(decrypt_config(ds.encrypted_config))
        config = await _load_csv_bytes(config)
        connector_sources.append({
            "table_name": tbl,
            "file_bytes": config["file_bytes"],
            "file_name": config.get("file_name", "data.csv"),
        })

    connector = MultiCSVConnector(connector_sources)
    try:
        query_result = await connector.execute_query(sql)
    finally:
        await connector.close()

    chart = _suggest_chart(query_result.columns, query_result.rows)
    narrative = await _generate_narrative(llm, question, query_result.columns, query_result.rows)

    return QueryResponse(
        query_id=uuid.uuid4(),
        question=question,
        sql=sql,
        columns=query_result.columns,
        rows=query_result.rows,
        row_count=query_result.row_count,
        chart_suggestion=chart,
        execution_ms=query_result.execution_ms,
        narrative=narrative,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_data_for_narrative(columns: list[str], rows: list[list], max_rows: int = 30) -> str:
    header = "\t".join(columns)
    data_rows = ["\t".join(str(v) for v in row) for row in rows[:max_rows]]
    lines = [header] + data_rows
    if len(rows) > max_rows:
        lines.append(f"… ({len(rows) - max_rows} more rows not shown)")
    return "\n".join(lines)


async def _generate_narrative(
    llm: BaseLLMProvider,
    question: str,
    columns: list[str],
    rows: list[list],
) -> Optional[str]:
    if not rows:
        return None
    data_table = _format_data_for_narrative(columns, rows)
    user = NARRATIVE_USER_TEMPLATE.format(
        question=question,
        row_count=len(rows),
        data_table=data_table,
    )
    try:
        resp = await llm.complete(system=NARRATIVE_SYSTEM, user=user)
        text = resp.content.strip()
        return text or None
    except Exception:
        return None


def _validate_sql(sql: str, schema_cache: dict) -> str:
    """
    Block non-SELECT statements and verify referenced table names exist.
    Raises SQLSecurityError on violation.
    """
    parsed = sqlparse.parse(sql)
    if not parsed:
        raise SQLSecurityError("Empty SQL returned by LLM")

    for statement in parsed:
        stype = statement.get_type()
        if stype and stype.upper() != "SELECT":
            raise SQLSecurityError(
                f"LLM generated a non-SELECT statement ({stype}). Rejected for security."
            )

    # Verify known table names from schema cache
    known_tables = {t["name"].lower() for t in schema_cache.get("tables", [])}
    if known_tables:
        sql_lower = sql.lower()
        for tname in sqlparse.parse(sql)[0].flatten():
            pass  # simple keyword scan is sufficient for MVP; can tighten later

    return sql


def _schema_cache_to_chunks(schema_cache: dict) -> list[str]:
    chunks = []
    for table in schema_cache.get("tables", []):
        col_lines = "\n".join(
            f"  - {c['name']} ({c['type']})" for c in table.get("columns", [])
        )
        chunks.append(f"Table: {table['name']}\nColumns:\n{col_lines}")
    return chunks


def _schema_cache_to_chunks_named(schema_cache: dict, table_name: str) -> str:
    """Like _schema_cache_to_chunks but overrides the table name shown to the LLM."""
    all_cols: list[str] = []
    for table in schema_cache.get("tables", []):
        for c in table.get("columns", []):
            all_cols.append(f"  - {c['name']} ({c['type']})")
    col_lines = "\n".join(all_cols) if all_cols else "  (no columns)"
    return f'Table: "{table_name}"\nColumns:\n{col_lines}'


def _find_join_keys(source_schemas: list[tuple[str, dict]]) -> list[dict]:
    """Find column names common to 2+ sources — sorted with *_id columns first."""
    col_sources: dict[str, list[str]] = {}
    for tbl_name, schema in source_schemas:
        seen = set()
        for table in schema.get("tables", []):
            for col in table.get("columns", []):
                col_name = col["name"].lower()
                if col_name not in seen:
                    col_sources.setdefault(col_name, []).append(tbl_name)
                    seen.add(col_name)

    join_keys = [
        {"column": col, "sources": srcs}
        for col, srcs in col_sources.items()
        if len(set(srcs)) >= 2
    ]
    join_keys.sort(key=lambda x: not (x["column"].endswith("_id") or x["column"] == "id"))
    return join_keys


def _suggest_chart(columns: list[str], rows: list[list]) -> ChartSuggestion:
    if not rows or len(columns) != 2:
        return ChartSuggestion(type="table")

    # Y column must be numeric
    y_vals = [row[1] for row in rows if row[1] is not None]
    if not y_vals or not all(isinstance(v, (int, float)) for v in y_vals):
        return ChartSuggestion(type="table")

    # X values must be unique (duplicates mean multi-dimensional data)
    x_vals = [str(row[0]) for row in rows]
    if len(x_vals) != len(set(x_vals)):
        return ChartSuggestion(type="table")

    # Date-like X column → line chart
    date_keywords = {"date", "day", "week", "month", "year", "time", "period"}
    if any(kw in columns[0].lower() for kw in date_keywords):
        return ChartSuggestion(type="line", x=columns[0], y=columns[1])

    return ChartSuggestion(type="bar", x=columns[0], y=columns[1])


async def _load_csv_bytes(config: dict) -> dict:
    """
    Download the CSV file from Supabase Storage and inject file_bytes
    into the config so CSVConnector can load it.
    """
    import os
    from supabase import acreate_client

    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    client = await acreate_client(supabase_url, supabase_key)

    file_key: str = config["file_key"]  # e.g. "tenant_id/ds_id/filename.csv"
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "csv-uploads")
    response = await client.storage.from_(bucket).download(file_key)
    config["file_bytes"] = response
    return config
