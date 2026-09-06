"""Add source-backed paper metadata and citation history.

Revision ID: 0011_add_paper_metadata
Revises: 0010_normalize_language_names
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011_add_paper_metadata"
down_revision = "0010_normalize_language_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benchmark_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("arxiv_id", sa.String(length=100), nullable=True),
        sa.Column("semantic_scholar_paper_id", sa.String(length=100), nullable=True),
        sa.Column("canonical_title", sa.Text(), nullable=True),
        sa.Column("authors", sa.Text(), nullable=True),
        sa.Column("venue", sa.String(length=255), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("is_open_access", sa.Boolean(), nullable=True),
        sa.Column("open_access_url", sa.Text(), nullable=True),
        sa.Column("metadata_source", sa.String(length=100), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column("citation_source", sa.String(length=100), nullable=True),
        sa.Column("citation_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["benchmark_id"], ["benchmarks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("benchmark_id"),
    )
    op.create_table(
        "citation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benchmark_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("citation_count", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_id"], ["benchmarks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citation_snapshots_benchmark_fetched", "citation_snapshots", ["benchmark_id", "fetched_at"])


def downgrade() -> None:
    op.drop_index("ix_citation_snapshots_benchmark_fetched", table_name="citation_snapshots")
    op.drop_table("citation_snapshots")
    op.drop_table("paper_metadata")
