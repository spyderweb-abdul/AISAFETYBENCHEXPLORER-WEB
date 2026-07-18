"""widen no_of_samples and license columns on benchmarks

Revision ID: 0002_widen_benchmark_cols
Revises: 0001_fix_extraction_fk
Create Date: 2026-07-18

Closes Known Gap #1 from PROJECT_ROADMAP.md Section 9 (open since
2026-07-12). A real extraction (PNAS implicit-bias paper,
doi:10.1073/pnas.2416228122) produced a legitimately detailed
no_of_samples value (253 characters) that exceeded benchmarks.
no_of_samples's VARCHAR(100) column width, causing a Postgres
StringDataRightTruncation error and rolling back an otherwise-good
INSERT.

This migration:
  - widens no_of_samples from VARCHAR(100) to TEXT
  - widens license from VARCHAR(100) to VARCHAR(300)
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_widen_benchmark_cols"
down_revision = "0001_fix_extraction_fk"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "benchmarks",
        "no_of_samples",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "benchmarks",
        "license",
        existing_type=sa.String(length=100),
        type_=sa.String(length=300),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "benchmarks",
        "license",
        existing_type=sa.String(length=300),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "benchmarks",
        "no_of_samples",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )