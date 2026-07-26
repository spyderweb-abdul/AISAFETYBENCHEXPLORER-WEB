"""add phase 4 verification columns to repo_stats

Revision ID: 0004_add_repo_stats_cols
Revises: 0003_add_repo_stats
Create Date: 2026-07-26

The repo_stats table already existed before Phase 4 (minimal schema:
id, benchmark_id, source, url, stars_or_likes, last_commit_at,
activity_status, fetched_at), created by an earlier migration. The
previous 0003 migration incorrectly assumed the table did not exist yet
and used op.create_table(), which either failed with
"relation repo_stats already exists" or was never actually applied.

This migration instead ADDS the missing Phase 4 verification columns to
the existing table, using one op.add_column() call per column (the
correct signature is add_column(table_name, column) -- it does not
accept a list of columns like create_table() does).

If 0003 was already marked as applied in your alembic_version table
despite never actually running, stamp down first:
    docker compose exec backend python -m alembic stamp 0002_widen_benchmark_cols
before running:
    docker compose exec backend python -m alembic upgrade head
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_add_repo_stats_cols"
down_revision = "0003_add_repo_stats"
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    sa.Column("owner", sa.String(length=200), nullable=True),
    sa.Column("name", sa.String(length=200), nullable=True),
    sa.Column("forks", sa.Integer(), nullable=True),
    sa.Column("open_issues", sa.Integer(), nullable=True),
    sa.Column("contributors_count", sa.Integer(), nullable=True),
    sa.Column("downloads", sa.Integer(), nullable=True),
    sa.Column("days_since_last_activity", sa.Integer(), nullable=True),
    sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("is_gated", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("license_id", sa.String(length=100), nullable=True),
    sa.Column("fetch_error", sa.Text(), nullable=True),
]


def upgrade() -> None:
    for column in _NEW_COLUMNS:
        op.add_column("repo_stats", column)

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


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS repository_activity_statistics")
    for column in reversed(_NEW_COLUMNS):
        op.drop_column("repo_stats", column.name)
