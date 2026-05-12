import io
import os
import time
import warnings

import duckdb

from .base import BaseConnector, ColumnInfo, QueryResult, SchemaInfo, TableInfo

ROW_LIMIT = 10_000


class CSVConnector(BaseConnector):
    """
    Loads a CSV/Excel file from Supabase Storage into an ephemeral DuckDB
    in-memory instance. The file is streamed into memory and never written
    to disk, keeping tenant data isolated per-request.

    config keys:
        file_bytes: raw file content as bytes  (set by the route after download)
        file_name:  original filename (used to detect Excel vs CSV)
    """

    def __init__(self, config: dict) -> None:
        self._file_bytes: bytes = config["file_bytes"]
        self._file_name: str = config.get("file_name", "data.csv")
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            import pandas as pd
            self._conn = duckdb.connect(database=":memory:")
            buf = io.BytesIO(self._file_bytes)
            ext = os.path.splitext(self._file_name)[1].lower()
            if ext in (".xlsx", ".xls"):
                df = pd.read_excel(buf)
            else:
                df = pd.read_csv(buf)
            # Promote string columns that look like dates to datetime so DuckDB
            # infers TIMESTAMP rather than VARCHAR — enables date functions.
            for col in df.select_dtypes(include=["object"]).columns:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        df[col] = pd.to_datetime(df[col])
                    except (ValueError, TypeError):
                        pass
            self._conn.register("_df_temp", df)
            self._conn.execute("CREATE TABLE data AS SELECT * FROM _df_temp")
        return self._conn

    async def test_connection(self) -> bool:
        try:
            self._get_conn().execute("SELECT 1")
            return True
        except Exception:
            return False

    async def introspect_schema(self) -> SchemaInfo:
        conn = self._get_conn()
        result = conn.execute("DESCRIBE data").fetchall()
        columns = [
            ColumnInfo(name=row[0], type=row[1], nullable=True)
            for row in result
        ]
        return SchemaInfo(
            tables=[TableInfo(name="data", columns=columns)],
            dialect="duckdb",
        )

    async def execute_query(self, sql: str, timeout_seconds: int = 30) -> QueryResult:
        safe_sql = _ensure_limit(sql, ROW_LIMIT)
        conn = self._get_conn()
        start = time.monotonic()
        rel = conn.execute(safe_sql)
        columns = [desc[0] for desc in rel.description]
        rows = [list(r) for r in rel.fetchall()]
        elapsed = int((time.monotonic() - start) * 1000)
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), execution_ms=elapsed)

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def _ensure_limit(sql: str, limit: int) -> str:
    if "LIMIT" not in sql.upper():
        return f"{sql.rstrip(';')} LIMIT {limit}"
    return sql
