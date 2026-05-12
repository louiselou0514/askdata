from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep, TenantScopedRepository
from app.models.glossary import BusinessGlossary

router = APIRouter(prefix="/glossary", tags=["glossary"])


class GlossaryEntry(BaseModel):
    id: uuid.UUID
    term: str
    definition: str


class CreateGlossaryEntry(BaseModel):
    term: str
    definition: str


@router.get("/", response_model=list[GlossaryEntry])
async def list_glossary(auth: CurrentUser, session: SessionDep) -> list[GlossaryEntry]:
    user, tenant = auth
    repo = TenantScopedRepository(session, tenant.id)
    entries = await repo.list(BusinessGlossary)
    return [GlossaryEntry(id=e.id, term=e.term, definition=e.definition) for e in entries]


@router.post("/", response_model=GlossaryEntry, status_code=status.HTTP_201_CREATED)
async def create_glossary_entry(
    body: CreateGlossaryEntry, auth: CurrentUser, session: SessionDep
) -> GlossaryEntry:
    user, tenant = auth
    entry = BusinessGlossary(
        id=uuid.uuid4(), tenant_id=tenant.id, term=body.term, definition=body.definition
    )
    session.add(entry)
    await session.commit()
    return GlossaryEntry(id=entry.id, term=entry.term, definition=entry.definition)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_glossary_entry(
    entry_id: uuid.UUID, auth: CurrentUser, session: SessionDep
) -> None:
    user, tenant = auth
    repo = TenantScopedRepository(session, tenant.id)
    entry = await repo.require(BusinessGlossary, entry_id)
    await session.delete(entry)
    await session.commit()
