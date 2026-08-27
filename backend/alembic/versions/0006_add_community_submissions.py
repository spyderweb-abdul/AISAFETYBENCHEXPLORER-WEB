"""add community submissions, notifications, provenance columns

Revision ID: 0006_add_community_submissions
Revises: 0005_add_job_failure_reason
Create Date: 2026-08-27

Phase 6 items 3 and 4: gated community submission workflow and
admin/submitter notifications.

Adds:
- benchmarks.submission_source (String(20), "admin" or "community",
  default "admin" so every existing row backfills correctly)
- benchmarks.submitted_by_user_id (UUID FK users.id, nullable) --
  real provenance identifier, distinct from created_by_user_id (which
  already exists and is stamped by the admin CRUD/agent_runner paths)
- users.is_trusted_submitter (Boolean, default False) -- admin-togglable
  flag; trusted submitters' failed domain checks are queued for manual
  review instead of auto-rejected (see app/core/submission_runner.py)
- submissions table: the community submission workflow record, one row
  per DOI a researcher submits, tracking domain-check outcome,
  extraction linkage, quality score snapshot, and admin decision
- notifications table: in-app notifications for admins (new submission
  queued) and submitters (approved/rejected/failed), with an optional
  best-effort email side channel (see app/core/notifications.py)

Destination path: backend/alembic/versions/0006_add_community_submissions.py
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_add_community_submissions"
down_revision = "0005_add_job_failure_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benchmarks",
        sa.Column("submission_source", sa.String(length=20), nullable=False, server_default="admin"),
    )
    op.add_column(
        "benchmarks",
        sa.Column(
            "submitted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column("is_trusted_submitter", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("submitter_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_value", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=False),
        # submitted -> extracting -> (domain_check_failed | pending_review | failed)
        #   -> (approved | rejected | needs_better_extraction)
        sa.Column("status", sa.String(length=30), nullable=False, server_default="submitted"),
        sa.Column("extraction_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extraction_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result_benchmark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmarks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("domain_check_passed", sa.Boolean(), nullable=True),
        sa.Column("domain_check_reason", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("admin_reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("admin_review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link_path", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("submissions")
    op.drop_column("users", "is_trusted_submitter")
    op.drop_column("benchmarks", "submitted_by_user_id")
    op.drop_column("benchmarks", "submission_source")
