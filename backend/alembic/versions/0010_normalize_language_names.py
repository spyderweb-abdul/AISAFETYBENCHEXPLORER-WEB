"""normalize benchmark language metadata to full language names

Revision ID: 0010_normalize_language_names
Revises: 0009_add_vocab_terms
Create Date: 2026-09-06

Language support is stored as a text array. Earlier records used ISO 639-1
codes while new extractions and UI controls use readable full labels. This
data-only migration preserves every array element while replacing the known
legacy codes with their canonical names.
"""

from alembic import op


revision = "0010_normalize_language_names"
down_revision = "0009_add_vocab_terms"
branch_labels = None
depends_on = None


_FORWARD_CASE = """
    CASE language_value
        WHEN 'en' THEN 'English'
        WHEN 'zh' THEN 'Chinese'
        WHEN 'ar' THEN 'Arabic'
        WHEN 'fr' THEN 'French'
        WHEN 'hi' THEN 'Hindi'
        WHEN 'ko' THEN 'Korean'
        ELSE language_value
    END
"""

_REVERSE_CASE = """
    CASE language_value
        WHEN 'English' THEN 'en'
        WHEN 'Chinese' THEN 'zh'
        WHEN 'Arabic' THEN 'ar'
        WHEN 'French' THEN 'fr'
        WHEN 'Hindi' THEN 'hi'
        WHEN 'Korean' THEN 'ko'
        ELSE language_value
    END
"""


def _replace_values(case_statement: str) -> None:
    op.execute(
        f"""
        UPDATE benchmarks
        SET language_support = ARRAY(
            SELECT {case_statement}
            FROM unnest(language_support) AS language_value
        )
        WHERE language_support && ARRAY['en', 'zh', 'ar', 'fr', 'hi', 'ko',
                                        'English', 'Chinese', 'Arabic', 'French', 'Hindi', 'Korean']::text[]
        """
    )


def upgrade() -> None:
    _replace_values(_FORWARD_CASE)


def downgrade() -> None:
    _replace_values(_REVERSE_CASE)
