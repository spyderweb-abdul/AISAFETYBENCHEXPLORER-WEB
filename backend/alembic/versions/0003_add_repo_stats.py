"""add repo_stats table

Revision ID: 0003_add_repo_stats
Revises: 0002_widen_benchmark_cols
Create Date: 2026-07-26

Alembic migration for Phase 4. Revision ID kept short (below 32 chars)
to avoid the alembic_version VARCHAR(32) truncation bug hit on
2026-07-18 (see PROJECT_ROADMAP.md Section 8).

Fixed 2026-07-26: op.add_column() takes exactly ONE column per call
(signature: add_column(table_name, column)), unlike op.create_table()
which accepts a list of columns as *args. The previous version of this
migration incorrectly passed 22 sa.Column(...) objects as separate
positional arguments to a single add_column() call, causing
"TypeError: add_column() takes 3 positional arguments but 23 were given".

This version creates the table fresh with op.create_table() (correct
API for defining a brand new table with many columns at once), matching
column-for-column the consolidated RepoStat model in app/models/orm.py
(single model, no duplicate RepoStats class).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_add_repo_stats"
down_revision = "0002_widen_benchmark_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
