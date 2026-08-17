"""add cost and token usage columns to extraction_jobs

Revision ID: 0005_add_extraction_cost_cols
Revises: 0004_add_repo_stats_cols
Create Date: 2026-08-15

Roadmap item 12: extraction_jobs had no columns for per-run token usage
or estimated cost, and no way to see run-to-run quality_score variance
for repeated runs of the same source_value. This migration adds the
token/cost columns; variance is computed on read (see
GET /extraction/jobs/variance in app/routers/extraction.py) from the
existing quality_score column across all jobs sharing a source_value,
so no new column is needed for variance itself.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_add_extraction_cost_cols"
down_revision = "0004_add_repo_stats_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extraction_jobs", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("extraction_jobs", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column(
        "extraction_jobs",
        sa.Column("estimated_cost_usd", sa.Numeric(10, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extraction_jobs", "estimated_cost_usd")
    op.drop_column("extraction_jobs", "output_tokens")
    op.drop_column("extraction_jobs", "input_tokens")
