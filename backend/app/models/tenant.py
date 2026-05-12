from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String)
    stripe_sub_id: Mapped[Optional[str]] = mapped_column(String)
    plan: Mapped[str] = mapped_column(String, default="trial")
    query_limit_monthly: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
