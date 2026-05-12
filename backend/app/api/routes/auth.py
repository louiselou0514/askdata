import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from typing import Annotated
from fastapi import Depends

from app.api.deps import SessionDep
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Tenant, User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    company_name: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, session: SessionDep) -> TokenResponse:
    # Check email not already taken across all tenants
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    slug = body.company_name.lower().replace(" ", "-")
    tenant = Tenant(id=uuid.uuid4(), name=body.company_name, slug=slug)
    session.add(tenant)
    await session.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        role="owner",
    )
    session.add(user)
    await session.commit()

    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(tenant.id),
        role=user.role,
    )
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == form.username))
    user: User | None = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    tenant = await session.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")

    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(tenant.id),
        role=user.role,
    )
    return TokenResponse(access_token=token)
