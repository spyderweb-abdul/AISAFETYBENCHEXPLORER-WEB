"""add model_options table (and merge the two existing alembic heads)

Revision ID: 0008_add_model_options
Revises: 0006_add_community_submissions, 0007_use_case_safety_dim_cols
Create Date: 2026-08-28

Adds model_options, the admin-manageable catalogue backing the Agent
Extraction Panel's model dropdown and the community submissions
re-extract dropdown (see backend/app/routers/models.py and
backend/app/models/orm.py's ModelOption). Seeds it with the 11 models
that were previously hardcoded in frontend/lib/modelOptions.ts and
admin/submissions/page.tsx's PAID_MODELS array.

MERGE NOTE: this repo currently has two divergent alembic heads that
were never reconciled:
  - 0006_add_community_submissions (Revises: 0005_add_job_failure_reason)
  - 0007_use_case_safety_dim_cols  (Revises: 0006_repo_stats_history_view)
Both ultimately trace back to 0004_add_repo_stats_cols via two
different, independently-created "0005_*" migrations
(0005_add_job_failure_reason and 0005_add_extraction_cost_cols), which
is how the branch happened -- neither author knew about the other's
0005 migration at the time. No merge migration existed before this one,
so `alembic upgrade head` would have failed with "Multiple head
revisions are present" the moment both branches were present in the
same checked-out repo. This migration's down_revision lists BOTH heads,
which is Alembic's standard merge pattern -- applying this migration
reconciles the branch AND adds model_options in a single step.

Destination path: backend/alembic/versions/0008_add_model_options.py
"""

from __future__ import annotations

import uuid as _uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_add_model_options"
down_revision = ("0006_add_community_submissions", "0007_use_case_safety_dim_cols")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("identifier", sa.String(length=100), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Seed with the models previously hardcoded in
    # frontend/lib/modelOptions.ts (MODEL_OPTIONS) and
    # admin/submissions/page.tsx (PAID_MODELS), so existing dropdowns
    # don't go empty the moment this migration is applied and the
    # frontend switches to fetching GET /models.
    model_options = sa.table(
        "model_options",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("identifier", sa.String),
        sa.column("provider", sa.String),
        sa.column("display_name", sa.String),
        sa.column("is_active", sa.Boolean),
    )

    seed_rows = [
        ("openai/gpt-4o", "openai", "GPT-4o"),
        ("openai/gpt-4o-mini", "openai", "GPT-4o mini"),
        ("anthropic/claude-sonnet-5", "anthropic", "Claude Sonnet 5"),
        ("anthropic/claude-opus-5", "anthropic", "Claude Opus 5"),
        ("anthropic/claude-haiku-4-5-20251001", "anthropic", "Claude Haiku 4.5"),
        ("ollama/deepseek-v4-pro", "ollama", "DeepSeek v4 Pro"),
        ("ollama/deepseek-v4-flash", "ollama", "DeepSeek v4 Flash"),
        ("ollama/kimi-k3", "ollama", "Kimi K3"),
        ("ollama/kimi-k2.6", "ollama", "Kimi K2.6"),
        ("ollama/qwen3.5:397b", "ollama", "Qwen 3.5 397B"),
        ("ollama/qwen3-coder:480b", "ollama", "Qwen 3 Coder 480B"),
    ]

    op.bulk_insert(
        model_options,
        [
            {
                "id": _uuid.uuid4(),
                "identifier": identifier,
                "provider": provider,
                "display_name": display_name,
                "is_active": True,
            }
            for identifier, provider, display_name in seed_rows
        ],
    )


def downgrade() -> None:
    op.drop_table("model_options")
    # NOTE: downgrading this migration only drops model_options -- it
    # does not and cannot "unmerge" the two heads back apart, since a
    # merge is a graph operation, not a schema change. If you need to
    # roll back past this point, `alembic downgrade` will walk back
    # down whichever of the two parent branches Alembic resolves first;
    # verify your target state manually with `alembic history` before
    # downgrading past a merge revision.
