"""repo_stats history support: index + latest-only view

Revision ID: 0006_repo_stats_history_view
Revises: 0005_add_extraction_cost_cols
Create Date: 2026-08-16

Roadmap item 15: app/core/tasks.py's _upsert_repo_stats() was renamed to
_insert_repo_stats_snapshot() and changed to always INSERT a new row
instead of updating one in place, so repo_stats is now an append-only
history table rather than only ever holding the latest fetched values.

No column changes are needed on repo_stats itself -- it already had
every column required, since the old code's "one row per benchmark_id
+ source" behavior was enforced entirely in application code, not by a
database constraint. This migration only:

1. Adds an index to keep "find the latest row per benchmark+source"
   queries fast as the table grows with history instead of staying at
   one row per benchmark+source forever.
2. Replaces the repository_activity_statistics view (created in
   migration 0004) so it continues to show exactly one row per
   benchmark+source (the latest), not a growing duplicate per snapshot
   -- otherwise any consumer of that view (future Phase 5/6 reporting)
   would silently start seeing inflated, duplicated rows the moment
   history accumulated.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_repo_stats_history_view"
down_revision = "0005_add_extraction_cost_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_repo_stats_benchmark_source_fetched",
        "repo_stats",
        ["benchmark_id", "source", "fetched_at"],
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW repository_activity_statistics AS
        SELECT
            latest.benchmark_id,
            latest.benchmark_name,
            latest.source,
            latest.owner,
            latest.name,
            latest.stars_or_likes,
            latest.forks,
            latest.downloads,
            latest.activity_status,
            latest.days_since_last_activity,
            latest.fetched_at
        FROM (
            SELECT
                b.id AS benchmark_id,
                b.benchmark_name,
                rs.source,
                rs.owner,
                rs.name,
                rs.stars_or_likes,
                rs.forks,
                rs.downloads,
                rs.activity_status,
                rs.days_since_last_activity,
                rs.fetched_at,
                ROW_NUMBER() OVER (
                    PARTITION BY rs.benchmark_id, rs.source
                    ORDER BY rs.fetched_at DESC
                ) AS rn
            FROM repo_stats rs
            JOIN benchmarks b ON b.id = rs.benchmark_id
        ) latest
        WHERE latest.rn = 1
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW repository_activity_statistics AS
        SELECT
            b.id AS benchmark_id,
            b.benchmark_name,
            rs.source,
            rs.owner,
            rs.name,
            rs.stars_or_likes,
            rs.forks,
            rs.downloads,
            rs.activity_status,
            rs.days_since_last_activity,
            rs.fetched_at
        FROM repo_stats rs
        JOIN benchmarks b ON b.id = rs.benchmark_id
        """
    )
    op.drop_index("ix_repo_stats_benchmark_source_fetched", table_name="repo_stats")
