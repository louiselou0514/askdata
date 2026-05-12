import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .base import BaseConnector, ColumnInfo, QueryResult, SchemaInfo, TableInfo

ROW_LIMIT = 10_000


class MySQLConnector(BaseConnector):
    def __init__(self, config: dict) -> None:
        self._url = (
            f"mysql+aiomysql://{config['user']}:{config['password']}"
            f"@{config['host']}:{config.get('port', 3306)}/{config['dbname']}"
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
            SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t
              ON c.TABLE_NAME = t.TABLE_NAME AND c.TABLE_SCHEMA = t.TABLE_SCHEMA
            WHERE c.TABLE_SCHEMA = DATABASE() AND t.TABLE_TYPE = 'BASE TABLE'
            ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
        """)
        tables: dict[str, TableInfo] = {}
        async with self._engine.connect() as conn:
            result = await conn.execute(sql)
            for row in result.mappings():
                tname = row["TABLE_NAME"]
                if tname not in tables:
                    tables[tname] = TableInfo(name=tname)
                tables[tname].columns.append(ColumnInfo(
                    name=row["COLUMN_NAME"],
                    type=row["DATA_TYPE"],
                    nullable=row["IS_NULLABLE"] == "YES",
                ))
        return SchemaInfo(tables=list(tables.values()), dialect="mysql")

    async def execute_query(self, sql: str, timeout_seconds: int = 30) -> QueryResult:
        safe_sql = _ensure_limit(sql, ROW_LIMIT)
        start = time.monotonic()
        async with self._engine.connect() as conn:
            await conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME={timeout_seconds * 1000}"))
            result = await conn.execute(text(safe_sql))
            rows = [list(r) for r in result.fetchall()]
            columns = list(result.keys())
        elapsed = int((time.monotonic() - start) * 1000)
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), execution_ms=elapsed)

    async def close(self) -> None:
        await self._engine.dispose()


def _ensure_limit(sql: str, limit: int) -> str:
    if "LIMIT" not in sql.upper():
        return f"{sql.rstrip(';')} LIMIT {limit}"
    return sql
