import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .base import BaseConnector, ColumnInfo, QueryResult, SchemaInfo, TableInfo

ROW_LIMIT = 10_000


class PostgresConnector(BaseConnector):
    def __init__(self, config: dict) -> None:
        # config keys: host, port, dbname, user, password
        self._url = (
            f"postgresql+asyncpg://{config['user']}:{config['password']}"
            f"@{config['host']}:{config.get('port', 5432)}/{config['dbname']}"
        )
        self._engine = create_async_engine(self._url, pool_size=1, max_overflow=0)

    async def test_connection(self) -> bool:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def introspect_schema(self) -> SchemaInfo:
        sql = text("""
            SELECT c.table_name, c.column_name, c.data_type, c.is_nullable
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON c.table_name = t.table_name AND c.table_schema = t.table_schema
            WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
            ORDER BY c.table_name, c.ordinal_position
        """)
        tables: dict[str, TableInfo] = {}
        async with self._engine.connect() as conn:
            result = await conn.execute(sql)
            for row in result.mappings():
                tname = row["table_name"]
                if tname not in tables:
                    tables[tname] = TableInfo(name=tname)
                tables[tname].columns.append(ColumnInfo(
                    name=row["column_name"],
                    type=row["data_type"],
                    nullable=row["is_nullable"] == "YES",
                ))
        return SchemaInfo(tables=list(tables.values()), dialect="postgresql")

    async def execute_query(self, sql: str, timeout_seconds: int = 30) -> QueryResult:
        safe_sql = _ensure_limit(sql, ROW_LIMIT)
        start = time.monotonic()
        async with self._engine.connect() as conn:
            await conn.execute(text(f"SET statement_timeout = {timeout_seconds * 1000}"))
            result = await conn.execute(text(safe_sql))
            rows = [list(r) for r in result.fetchall()]
            columns = list(result.keys())
        elapsed = int((time.monotonic() - start) * 1000)
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), execution_ms=elapsed)

    async def close(self) -> None:
        await self._engine.dispose()


def _ensure_limit(sql: str, limit: int) -> str:
    upper = sql.upper()
    if "LIMIT" not in upper:
        return f"{sql.rstrip(';')} LIMIT {limit}"
    return sql
