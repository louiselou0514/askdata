"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension — must exist before the vector column is created
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("slug", sa.String, nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String),
        sa.Column("stripe_sub_id", sa.String),
        sa.Column("plan", sa.String, default="trial"),
        sa.Column("query_limit_monthly", sa.Integer, default=100),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("role", sa.String, default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("source_type", sa.String, nullable=False),
        sa.Column("encrypted_config", sa.Text, nullable=False),
        sa.Column("schema_cache", postgresql.JSONB),
        sa.Column("schema_updated_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String, default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "schema_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        # vector(1536) for text-embedding-3-small
        sa.Column("embedding", sa.Text, nullable=False),  # raw DDL via execute below
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Replace the placeholder Text column with the real vector type
    op.execute("ALTER TABLE schema_embeddings ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector")

    # HNSW index for fast approximate nearest-neighbour search
    op.execute(
        "CREATE INDEX idx_schema_embeddings_hnsw "
        "ON schema_embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index("idx_schema_embeddings_tenant", "schema_embeddings", ["tenant_id"])

    op.create_table(
        "business_glossary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.Text, nullable=False),
        sa.Column("definition", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_sources.id", ondelete="SET NULL")),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("generated_sql", sa.Text),
        sa.Column("status", sa.String, default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("row_count", sa.Integer),
        sa.Column("execution_ms", sa.Integer),
        sa.Column("llm_tokens_used", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_queries_tenant", "queries", ["tenant_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB),
    )
    op.create_index("idx_usage_events_tenant", "usage_events", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("usage_events")
    op.drop_table("queries")
    op.drop_table("business_glossary")
    op.drop_table("schema_embeddings")
    op.drop_table("data_sources")
    op.drop_table("users")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS vector")
