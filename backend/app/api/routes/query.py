from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

import duckdb

from app.api.deps import CurrentUser, SessionDep
from app.models.query import Query as QueryModel
from app.services.llm import get_llm_provider
from app.services.nl_to_sql import (
    SQLSecurityError,
    UnableToAnswerError,
    run_query,
)

router = APIRouter(prefix="/query", tags=["query"])


class QueryHistoryItem(BaseModel):
    id: uuid.UUID
    question: str
    status: str
    row_count: Optional[int] = None
    execution_ms: Optional[int] = None
    created_at: datetime
    data_source_id: Optional[uuid.UUID] = None


class QueryRequest(BaseModel):
    question: str
    data_source_ids: list[uuid.UUID]


class ChartSuggestionOut(BaseModel):
    type: str
    x: Optional[str] = None
    y: Optional[str] = None


class QueryResponse(BaseModel):
    query_id: uuid.UUID
    question: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    chart_suggestion: ChartSuggestionOut
    execution_ms: int
    narrative: Optional[str] = None


@router.post("/", response_model=QueryResponse)
async def execute_query(
    body: QueryRequest,
    auth: CurrentUser,
    session: SessionDep,
) -> QueryResponse:
    user, tenant = auth
    llm = get_llm_provider()

    try:
        result = await run_query(
            session=session,
            llm=llm,
            tenant_id=tenant.id,
            user_id=user.id,
            data_source_ids=body.data_source_ids,
            question=body.question,
        )
    except UnableToAnswerError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except SQLSecurityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except duckdb.Error as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Query execution failed: {exc}")

    return QueryResponse(
        query_id=result.query_id,
        question=result.question,
        sql=result.sql,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        chart_suggestion=ChartSuggestionOut(
            type=result.chart_suggestion.type,
            x=result.chart_suggestion.x,
            y=result.chart_suggestion.y,
        ),
        execution_ms=result.execution_ms,
        narrative=result.narrative,
    )


@router.get("/history", response_model=list[QueryHistoryItem])
async def get_query_history(
    auth: CurrentUser,
    session: SessionDep,
    data_source_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> list[QueryHistoryItem]:
    user, tenant = auth
    stmt = (
        select(QueryModel)
        .where(QueryModel.tenant_id == tenant.id, QueryModel.status == "success")
    )
    if data_source_id:
        stmt = stmt.where(QueryModel.data_source_id == data_source_id)
    stmt = stmt.order_by(QueryModel.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        QueryHistoryItem(
            id=r.id,
            question=r.question,
            status=r.status,
            row_count=r.row_count,
            execution_ms=r.execution_ms,
            created_at=r.created_at,
            data_source_id=r.data_source_id,
        )
        for r in rows
    ]
