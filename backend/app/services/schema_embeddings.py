from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import SchemaInfo
from app.models import DataSource, SchemaEmbedding
from app.services.llm import BaseLLMProvider


def _schema_to_chunks(schema: SchemaInfo) -> list[str]:
    """Convert a SchemaInfo into one text chunk per table for embedding."""
    chunks = []
    for table in schema.tables:
        col_lines = "\n".join(
            f"  - {c.name} ({c.type}{', nullable' if c.nullable else ''})"
            for c in table.columns
        )
        chunks.append(f"Table: {table.name}\nColumns:\n{col_lines}")
    return chunks


async def refresh_embeddings(
    session: AsyncSession,
    llm: BaseLLMProvider,
    data_source: DataSource,
    file_bytes: Optional[bytes] = None,
) -> None:
    """
    Re-introspect the data source schema, embed each table chunk,
    and replace all stored embeddings for this data source.
    """
    from app.connectors.base import ConnectorFactory
    from app.core.security import decrypt_config
    import json

    config = json.loads(decrypt_config(data_source.encrypted_config))
    if file_bytes is not None:
        config["file_bytes"] = file_bytes
    connector = ConnectorFactory.create(data_source.source_type, config)
    try:
        schema = await connector.introspect_schema()
    finally:
        await connector.close()

    chunks = _schema_to_chunks(schema)

    # Delete old embeddings for this data source
    await session.execute(
        delete(SchemaEmbedding).where(SchemaEmbedding.data_source_id == data_source.id)
    )

    for chunk in chunks:
        vector = await llm.embed(chunk)
        session.add(SchemaEmbedding(
            id=uuid.uuid4(),
            data_source_id=data_source.id,
            tenant_id=data_source.tenant_id,
            chunk_text=chunk,
            embedding=vector,
        ))

    # Update schema cache and timestamp on the data source
    data_source.schema_cache = {
        "tables": [
            {"name": t.name, "columns": [{"name": c.name, "type": c.type} for c in t.columns]}
            for t in schema.tables
        ],
        "dialect": schema.dialect,
    }
    data_source.schema_updated_at = datetime.now(timezone.utc)
    data_source.status = "connected"
    await session.commit()


async def retrieve_relevant_chunks(
    session: AsyncSession,
    llm: BaseLLMProvider,
    tenant_id: uuid.UUID,
    data_source_id: uuid.UUID,
    question: str,
    top_k: int = 10,
) -> list[str]:
    """
    Embed the question and return the top_k most relevant schema chunks
    for this tenant+data_source via pgvector cosine similarity.
    """
    from sqlalchemy import text

    question_vector = await llm.embed(question)
    vector_str = "[" + ",".join(str(x) for x in question_vector) + "]"

    sql = text("""
        SELECT chunk_text
        FROM schema_embeddings
        WHERE tenant_id = :tenant_id AND data_source_id = :ds_id
        ORDER BY embedding <=> CAST(:vec AS vector)
        LIMIT :k
    """)
    result = await session.execute(sql, {
        "tenant_id": tenant_id,
        "ds_id": data_source_id,
        "vec": vector_str,
        "k": top_k,
    })
    return [row[0] for row in result.fetchall()]
