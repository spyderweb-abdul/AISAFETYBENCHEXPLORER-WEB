"""fix extraction_jobs result_benchmark_id FK to allow benchmark delete

Revision ID: 0001_fix_extraction_fk
Revises: None
Create Date: 2026-07-18

The extraction_jobs.result_benchmark_id foreign key was created (via
schema.sql) with no ON DELETE behavior, which defaults to Postgres
NO ACTION and blocks deleting any benchmark that was ever the result of
an agent extraction job:

    psycopg2.errors.ForeignKeyViolation: update or delete on table
    "benchmarks" violates foreign key constraint
    "extraction_jobs_result_benchmark_id_fkey" on table "extraction_jobs"

Fix: change the FK to ON DELETE SET NULL. Deleting a benchmark now nulls
out extraction_jobs.result_benchmark_id instead of being blocked, so the
job's own history (source_type, source_value, model_used, quality_score,
status, timestamps) is preserved as an audit trail even after the
resulting benchmark record is deleted.

This is the first Alembic migration in this project (schema.sql is
currently loaded directly via psql per the README, not through Alembic
history), so down_revision is None.

Uses the actual constraint name Postgres auto-generated
("extraction_jobs_result_benchmark_id_fkey") when the table was first
created from schema.sql. If your database has a differently-named
constraint, run `\d extraction_jobs` in psql to confirm before applying.
"""
from alembic import op

revision = "0001_fix_extraction_fk"
down_revision = None
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "extraction_jobs_result_benchmark_id_fkey"


def upgrade():
    op.drop_constraint(CONSTRAINT_NAME, "extraction_jobs", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT_NAME,
        source_table="extraction_jobs",
        referent_table="benchmarks",
        local_cols=["result_benchmark_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(CONSTRAINT_NAME, "extraction_jobs", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT_NAME,
        source_table="extraction_jobs",
        referent_table="benchmarks",
        local_cols=["result_benchmark_id"],
        remote_cols=["id"],
    )