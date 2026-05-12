from __future__ import annotations

import io
import re
import time
import warnings
from typing import Any

import duckdb

from .base import BaseConnector, ColumnInfo, QueryResult, SchemaInfo, TableInfo
from .csv import ROW_LIMIT, _ensure_limit


# Common SQL/DuckDB reserved words that cause parse errors when used unquoted as table names
_RESERVED = {
    "order", "group", "select", "from", "where", "join", "table", "index",
    "values", "insert", "update", "delete", "create", "drop", "alter",
    "column", "primary", "key", "foreign", "default", "null", "and", "or",
    "not", "in", "is", "by", "as", "with", "union", "having", "case",
    "when", "then", "else", "end", "all", "any", "exists", "distinct",
}


def sanitize_table_name(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]", "_", name.lower()).strip("_") or "tbl"
    if s[0].isdigit():
        s = "t_" + s
    if s in _RESERVED:
        s = s + "_tbl"
    return s


def deduplicate_table_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for name in names:
        base = sanitize_table_name(name)
        if base in seen:
            seen[base] += 1
            result.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            result.append(base)
    return result


class MultiCSVConnector(BaseConnector):
    """
    Loads multiple CSV/Excel files as separate named tables in a single
    in-memory DuckDB instance, enabling cross-table JOIN queries.

    Each entry in `sources` must have:
        table_name: str          sanitized table name to register
        file_bytes: bytes        raw file content
        file_name: str           original filename (for xlsx detection)
    """

    def __init__(self, sources: list[dict[str, Any]]) -> None:
        self._sources = sources
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is not None:
            return self._conn

        import pandas as pd

        self._conn = duckdb.connect(database=":memory:")
        for source in self._sources:
            tbl = source["table_name"]
            buf = io.BytesIO(source["file_bytes"])
            ext = source.get("file_name", "").rsplit(".", 1)[-1].lower()
            df = pd.read_excel(buf) if ext in ("xlsx", "xls") else pd.read_csv(buf)

            for col in df.select_dtypes(include=["object"]).columns:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        df[col] = pd.to_datetime(df[col])
                    except (ValueError, TypeError):
                        pass

            tmp = f"_tmp_{tbl}"
            self._conn.register(tmp, df)
            self._conn.execute(f'CREATE TABLE "{tbl}" AS SELECT * FROM "{tmp}"')
            self._conn.unregister(tmp)

        return self._conn

    async def test_connection(self) -> bool:
        try:
            self._get_conn().execute("SELECT 1")
            return True
        except Exception:
            return False

    async def introspect_schema(self) -> SchemaInfo:
        conn = self._get_conn()
        tables = []
        for source in self._sources:
            tbl = source["table_name"]
            rows = conn.execute(f'DESCRIBE "{tbl}"').fetchall()
            columns = [ColumnInfo(name=r[0], type=r[1], nullable=True) for r in rows]
            tables.append(TableInfo(name=tbl, columns=columns))
        return SchemaInfo(tables=tables, dialect="duckdb")

    async def execute_query(self, sql: str, timeout_seconds: int = 30) -> QueryResult:
        safe_sql = _ensure_limit(sql, ROW_LIMIT)
        conn = self._get_conn()
        start = time.monotonic()
        rel = conn.execute(safe_sql)
        columns = [d[0] for d in rel.description]
        rows = [list(r) for r in rel.fetchall()]
        elapsed = int((time.monotonic() - start) * 1000)
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), execution_ms=elapsed)

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
