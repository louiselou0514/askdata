from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool = True


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass
class SchemaInfo:
    tables: list[TableInfo]
    dialect: str  # postgresql | mysql | duckdb


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_ms: int


class BaseConnector(ABC):
    @abstractmethod
    async def test_connection(self) -> bool:
        """Return True if the data source is reachable."""

    @abstractmethod
    async def introspect_schema(self) -> SchemaInfo:
        """Return the full schema of the data source."""

    @abstractmethod
    async def execute_query(self, sql: str, timeout_seconds: int = 30) -> QueryResult:
        """Execute a SELECT query and return results."""

    @abstractmethod
    async def close(self) -> None:
        """Release any held resources."""


class ConnectorFactory:
    @staticmethod
    def create(source_type: str, config: dict) -> BaseConnector:
        if source_type == "postgres":
            from .postgres import PostgresConnector
            return PostgresConnector(config)
        elif source_type == "mysql":
            from .mysql import MySQLConnector
            return MySQLConnector(config)
        elif source_type == "csv":
            from .csv import CSVConnector
            return CSVConnector(config)
        elif source_type == "google_sheets":
            from .sheets import GoogleSheetsConnector
            return GoogleSheetsConnector(config)
        else:
            raise ValueError(f"Unknown source type: {source_type!r}")
