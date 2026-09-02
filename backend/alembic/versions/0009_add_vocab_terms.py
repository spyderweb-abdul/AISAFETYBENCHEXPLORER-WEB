"""add vocab_terms table

Revision ID: 0009_add_vocab_terms
Revises: 0008_add_model_options
Create Date: 2026-09-01

Adds vocab_terms, the admin-manageable, agent-grown catalogue of
task_type and evaluation_metric terms (see backend/app/models/orm.py's
VocabTerm and backend/app/routers/vocab_terms.py). agent_runner.py
fetches active/canonical terms per category to guide (not constrain)
the extraction prompt, and upserts newly-seen terms after every
successful extraction.

Seeds task_type with the 60-item KNOWN_TASK_TYPES list that was
previously hardcoded in agent_runner.py (the more complete of the two
independently-drifted copies -- see PROJECT_ROADMAP.md's Known Gap 19
for the analogous USE_CASES drift bug this mirrors). Seeds
evaluation_metric with a small set of widely-recognized starting
metrics; the vast majority of evaluation_metric terms are expected to
grow organically from real extractions rather than be pre-seeded,
since metric naming is intentionally paper-terminology-driven, not a
closed vocabulary.

Destination path: backend/alembic/versions/0009_add_vocab_terms.py
"""

from __future__ import annotations

import uuid as _uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_add_vocab_terms"
down_revision = "0008_add_model_options"
branch_labels = None
depends_on = None


_FALLBACK_TASK_TYPES = [
    "Safety", "Adversarial", "Adversarial Method", "Red Teaming", "Jailbreak",
    "Attack Eval", "Robustness", "Vulnerability", "Risk Assessment",
    "Bias", "Fairness", "Stereotype", "Gender", "Social", "Sociodemographics",
    "Cultural", "Norm Alignment",
    "Factuality", "Factual Consistency", "Hallucination", "Truthfulness",
    "Grounding", "Faithfulness", "Claim Verification",
    "Toxicity", "Harmfulness", "Hate Speech", "Content Moderation",
    "Hazardous", "Hazardous Knowledge", "Physical Safety", "Medical Safety",
    "Alignment", "Value Alignment", "Moral", "Trustworthiness",
    "Helpfulness Eval", "Preference Eval", "Satisfaction Eval",
    "Privacy", "Prompt Extraction", "Cyberattacks", "Unlearning",
    "Agents Safety", "Agents Behavior Detection", "Reasoning",
    "Refusal", "False Refusal", "Over Refusal", "Non-compliance",
    "Consistency", "Calibration",
    "Instruction-following", "Rule-following", "RAG", "Multimodal",
    "Conversational Safety", "Opinion Steering", "Causal Reasoning",
    "Benchmark", "Evaluation", "Crowdsourced", "Lie Detection",
    "Capabilities", "Language",
]

_SEED_EVAL_METRICS = [
    "Accuracy", "F1 Score", "Precision", "Recall", "Exact Match",
    "Attack Success Rate", "Refusal Rate", "BLEU", "ROUGE-L",
    "Mean Absolute Error (MAE)", "Spearman Correlation", "Pearson Correlation",
    "AUROC", "Win Rate", "Pass@k",
]


def _normalize(term: str) -> str:
    return " ".join(term.strip().lower().split())


def upgrade() -> None:
    op.create_table(
        "vocab_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("term", sa.String(length=255), nullable=False),
        sa.Column("normalized_term", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_canonical", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("canonical_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "first_seen_benchmark_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("benchmarks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="agent"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_foreign_key(
        "fk_vocab_terms_canonical_term_id",
        "vocab_terms", "vocab_terms",
        ["canonical_term_id"], ["id"],
    )
    op.create_unique_constraint(
        "uq_vocab_terms_category_normalized_term",
        "vocab_terms", ["category", "normalized_term"],
    )
    op.create_index("ix_vocab_terms_category", "vocab_terms", ["category"])

    vocab_terms = sa.table(
        "vocab_terms",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("category", sa.String),
        sa.column("term", sa.String),
        sa.column("normalized_term", sa.String),
        sa.column("source", sa.String),
        sa.column("usage_count", sa.Integer),
    )

    seed_rows = [
        {"category": "task_type", "term": t, "normalized_term": _normalize(t)}
        for t in _FALLBACK_TASK_TYPES
    ] + [
        {"category": "evaluation_metric", "term": t, "normalized_term": _normalize(t)}
        for t in _SEED_EVAL_METRICS
    ]

    op.bulk_insert(
        vocab_terms,
        [
            {
                "id": _uuid.uuid4(),
                "category": row["category"],
                "term": row["term"],
                "normalized_term": row["normalized_term"],
                "source": "admin",
                "usage_count": 1,
            }
            for row in seed_rows
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_vocab_terms_category", table_name="vocab_terms")
    op.drop_constraint("uq_vocab_terms_category_normalized_term", "vocab_terms", type_="unique")
    op.drop_constraint("fk_vocab_terms_canonical_term_id", "vocab_terms", type_="foreignkey")
    op.drop_table("vocab_terms")
