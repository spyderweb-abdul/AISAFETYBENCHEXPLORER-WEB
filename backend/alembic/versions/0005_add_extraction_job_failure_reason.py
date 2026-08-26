"""add failure_reason to extraction_jobs

Revision ID: 0005_add_job_failure_reason
Revises: 0004_add_repo_stats_cols
Create Date: 2026-08-25

Known Gap item 17 (Ollama Cloud subscription blocker): extraction_jobs
had no column to persist a human-readable reason when a job's
status becomes "failed" -- run_extraction()'s except block only wrote
"failed" to job.status and logged the exception via logger.exception(),
so the actual cause (e.g. Ollama Cloud's 403 "this model requires a
subscription" error) was visible only in backend logs, not to anyone
looking at the job in the admin frontend or via GET /extraction/jobs.

This migration adds a single nullable Text column, failure_reason,
populated by agent_runner.py's generic except block on every failure
(not just the Ollama Cloud case), so any future failure mode also
becomes visible without a log dive. See app/core/agent_runner.py's
_wrap_provider_error() and the updated except block for the write side,
and app/schemas/extraction_job.py's ExtractionJobOut for the read side.

Destination path: backend/alembic/versions/0005_add_extraction_job_failure_reason.py
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_add_job_failure_reason"
down_revision = "0004_add_repo_stats_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extraction_jobs",
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extraction_jobs", "failure_reason")
