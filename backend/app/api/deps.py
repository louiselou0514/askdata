from __future__ import annotations

import uuid
from typing import Annotated, Any, TypeVar

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Tenant, User

M = TypeVar("M")

_DEV_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DEV_USER_ID   = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> tuple[User, Tenant]:
    tenant = await session.get(Tenant, _DEV_TENANT_ID)
    if not tenant:
        tenant = Tenant(id=_DEV_TENANT_ID, name="Dev", slug="dev")
        session.add(tenant)
        await session.flush()

    user = await session.get(User, _DEV_USER_ID)
    if not user:
        user = User(
            id=_DEV_USER_ID,
            tenant_id=_DEV_TENANT_ID,
            email="dev@local",
            hashed_password="",
            role="owner",
        )
        session.add(user)
        await session.flush()

    await session.commit()
    return user, tenant


CurrentUser = Annotated[tuple[User, Tenant], Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


class TenantScopedRepository:
    """
    Base repository that hard-scopes every SELECT to the current tenant.
    Prevents horizontal privilege escalation: a user who guesses another
    tenant's resource UUID gets a 404, not a 403, to avoid information leakage.
    """

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get(self, model: type[M], resource_id: uuid.UUID) -> M | None:
        result = await self._session.execute(
            select(model).where(
                model.id == resource_id,
                model.tenant_id == self._tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, model: type[M], **filters: Any) -> list[M]:
        stmt = select(model).where(model.tenant_id == self._tenant_id)
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def require(self, model: type[M], resource_id: uuid.UUID) -> M:
        obj = await self.get(model, resource_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return obj
