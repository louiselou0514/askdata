import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class Query(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "queries"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    data_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    row_count: Mapped[Optional[int]] = mapped_column(Integer)
    execution_ms: Mapped[Optional[int]] = mapped_column(Integer)
    llm_tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
