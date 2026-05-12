from __future__ import annotations

import time

import duckdb
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .base import BaseConnector, ColumnInfo, QueryResult, SchemaInfo, TableInfo

ROW_LIMIT = 10_000


class GoogleSheetsConnector(BaseConnector):
    """
    Fetches a Google Sheet via the Sheets API, loads the data into an
    ephemeral DuckDB instance, and executes SQL against it.

    config keys:
        spreadsheet_id, oauth_token (dict with token/refresh_token/etc.)
    """

    def __init__(self, config: dict) -> None:
        self._spreadsheet_id: str = config["spreadsheet_id"]
        self._creds = Credentials(
            token=config["oauth_token"].get("token"),
            refresh_token=config["oauth_token"].get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=config["oauth_token"].get("client_id"),
            client_secret=config["oauth_token"].get("client_secret"),
        )
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _refresh_creds(self) -> None:
        if self._creds.expired and self._creds.refresh_token:
            self._creds.refresh(Request())

    def _fetch_sheet_data(self) -> list[list]:
        self._refresh_creds()
        service = build("sheets", "v4", credentials=self._creds)
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range="A1:ZZ")
            .execute()
        )
        return result.get("values", [])

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            rows = self._fetch_sheet_data()
            if not rows:
                raise ValueError("Google Sheet is empty")
            import pandas as pd
            headers = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=headers)
            self._conn = duckdb.connect(database=":memory:")
            self._conn.register("data", df)
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
        columns = [ColumnInfo(name=row[0], type=row[1], nullable=True) for row in result]
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
