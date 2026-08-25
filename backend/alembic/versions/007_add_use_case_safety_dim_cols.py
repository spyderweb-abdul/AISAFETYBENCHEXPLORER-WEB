"""add use_cases and safety_dimensions columns to benchmarks

Revision ID: 0007_use_case_safety_dim_cols
Revises: 0006_repo_stats_history_view
Create Date: 2026-08-23

Phase 5: adds two new array columns to benchmarks, computed
deterministically by app/core/use_case_classifier.py and
app/core/safety_dimension_classifier.py at extraction time (see
agent_runner_use_case_patch.md) and on every manual create/update (see
app/routers/benchmarks.py). Existing rows are backfilled by
app/scripts/backfill_use_case_safety_dimensions.py after this migration
is applied -- the columns default to an empty array so the migration
itself does not need to compute anything.

FIX (2026-08-23): the first version of this migration used revision id
"0007_add_use_case_safety_dim_cols" (33 characters), which exceeded
Alembic's own alembic_version.version_num column width
(VARCHAR(32)) and failed with StringDataRightTruncation when Alembic
tried to record it -- the exact same failure mode already documented
in PROJECT_ROADMAP.md's 2026-07-18 Change Log entries for migrations
0001/0002, which should have been checked against before naming this
one. Shortened to "0007_use_case_safety_dim_cols" (29 characters).
Since this failed on Alembic's own bookkeeping insert, not the
op.add_column() calls themselves, and Alembic runs under transactional
DDL, the entire transaction (including those two ADD COLUMN statements)
rolled back cleanly -- no partial state to clean up, just re-run
`alembic upgrade head` with this corrected file in place of the
original.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0007_use_case_safety_dim_cols"
down_revision = "0006_repo_stats_history_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benchmarks",
        sa.Column("use_cases", ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "benchmarks",
        sa.Column("safety_dimensions", ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("benchmarks", "safety_dimensions")
    op.drop_column("benchmarks", "use_cases")
