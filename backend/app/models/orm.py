import uuid
from datetime import datetime
from sqlalchemy import (
    ARRAY, Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text, func
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()

complexity_enum = ENUM("Popular", "High", "Medium", "Low", "Unknown", name="complexity_enum", create_type=False)
created_by_enum = ENUM("Human", "Machine", "Hybrid", name="created_by_enum", create_type=False)
dev_purpose_enum = ENUM("Eval", "Train", "Train & Eval", name="dev_purpose_enum", create_type=False)
integration_enum = ENUM("API", "Export", "API & Export", "NA", name="integration_enum", create_type=False)
code_dataset_enum = ENUM("Yes", "No", name="code_dataset_enum", create_type=False)
user_role_enum = ENUM("admin", "researcher", name="user_role_enum", create_type=False)
job_status_enum = ENUM("queued", "running", "done", "failed", "needs_review", name="job_status_enum", create_type=False)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(user_role_enum, nullable=False, default="researcher")
    github_id = Column(String(64))
    is_trusted_submitter = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benchmark_name = Column(String(255), nullable=False)
    task_type = Column(ARRAY(Text), nullable=False, default=list)
    benchmark_paper_title = Column(Text, nullable=False)
    release_date = Column(Date)
    description = Column(Text)
    code_dataset = Column(code_dataset_enum, default="No")
    no_of_samples = Column(String(100))
    created_by = Column(created_by_enum)
    entry_modalities = Column(ARRAY(Text), nullable=False, default=list)
    dev_purpose = Column(dev_purpose_enum)
    license = Column(String(100))
    evaluation_metrics = Column(ARRAY(Text), nullable=False, default=list)
    complexity_level = Column(complexity_enum, default="Unknown")
    complexity_justification = Column(Text)
    language_support = Column(ARRAY(Text), nullable=False, default=list)
    integration_option = Column(integration_enum, default="NA")
    citation_range = Column(String(50))
    cited_by = Column(Integer, default=0)
    code_repository = Column(Text)
    dataset_repository = Column(Text)
    paper_link = Column(Text)
    status = Column(String(30), nullable=False, default="published")
    use_cases = Column(ARRAY(Text), nullable=False, default=list)
    safety_dimensions = Column(ARRAY(Text), nullable=False, default=list)
    submission_source = Column(String(20), nullable=False, default="admin")
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    metrics = relationship("EvalMetric", back_populates="benchmark", cascade="all, delete-orphan")
    repo_stats = relationship("RepoStat", back_populates="benchmark", cascade="all, delete-orphan")
    paper_metadata = relationship("PaperMetadata", back_populates="benchmark", uselist=False, cascade="all, delete-orphan")
    citation_snapshots = relationship("CitationSnapshot", back_populates="benchmark", cascade="all, delete-orphan")

class EvalMetric(Base):
    __tablename__ = "eval_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False)
    benchmark_name = Column(String(255), nullable=False)
    paper_title = Column(Text, nullable=False)
    paper_link = Column(Text)
    metric_name = Column(String(255), nullable=False)
    conceptual_description = Column(Text)
    methodological_details = Column(Text)
    mathematical_definition = Column(Text)
    differences_from_standard_definition = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    benchmark = relationship("Benchmark", back_populates="metrics")


class RepoStat(Base):
    __tablename__ = "repo_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(20), nullable=False)
    url = Column(Text, nullable=False)
    owner = Column(String(200), nullable=True)
    name = Column(String(200), nullable=True)
    stars_or_likes = Column(Integer, default=0)
    forks = Column(Integer, nullable=True)
    open_issues = Column(Integer, nullable=True)
    contributors_count = Column(Integer, nullable=True)
    downloads = Column(Integer, nullable=True)
    last_commit_at = Column(DateTime(timezone=True))
    days_since_last_activity = Column(Integer, nullable=True)
    activity_status = Column(String(30))
    is_archived = Column(Boolean, nullable=False, default=False)
    is_private = Column(Boolean, nullable=False, default=False)
    is_gated = Column(Boolean, nullable=False, default=False)
    license_id = Column(String(100), nullable=True)
    fetch_error = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    benchmark = relationship("Benchmark", back_populates="repo_stats")


class PaperMetadata(Base):
    """Latest source-backed bibliographic metadata for one benchmark paper."""

    __tablename__ = "paper_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False, unique=True)
    doi = Column(String(255), nullable=True)
    arxiv_id = Column(String(100), nullable=True)
    semantic_scholar_paper_id = Column(String(100), nullable=True)
    canonical_title = Column(Text, nullable=True)
    authors = Column(Text, nullable=True)
    venue = Column(String(255), nullable=True)
    publication_date = Column(Date, nullable=True)
    is_open_access = Column(Boolean, nullable=True)
    open_access_url = Column(Text, nullable=True)
    metadata_source = Column(String(100), nullable=True)
    citation_count = Column(Integer, nullable=True)
    citation_source = Column(String(100), nullable=True)
    citation_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_refreshed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_error = Column(Text, nullable=True)

    benchmark = relationship("Benchmark", back_populates="paper_metadata")


class CitationSnapshot(Base):
    """Append-only citation-count history, intentionally separate from repo stats."""

    __tablename__ = "citation_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False)
    citation_count = Column(Integer, nullable=False)
    source = Column(String(100), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    benchmark = relationship("Benchmark", back_populates="citation_snapshots")


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(20), nullable=False)
    source_value = Column(Text, nullable=False)
    model_used = Column(String(100))
    status = Column(job_status_enum, nullable=False, default="queued")
    quality_score = Column(Numeric(3, 2))
    requires_review = Column(Boolean, default=True)
    result_benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="SET NULL"))
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Numeric(10, 4), nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submitter_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source_type = Column(String(20), nullable=False)
    source_value = Column(Text, nullable=False)
    model_used = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="submitted")
    extraction_job_id = Column(UUID(as_uuid=True), ForeignKey("extraction_jobs.id", ondelete="SET NULL"))
    result_benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="SET NULL"))
    domain_check_passed = Column(Boolean, nullable=True)
    domain_check_reason = Column(Text, nullable=True)
    quality_score = Column(Numeric(3, 2), nullable=True)
    admin_reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    admin_review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    link_path = Column(String(255), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelOption(Base):
    """Admin-manageable catalogue of models offered in the Agent
    Extraction Panel and the community submissions re-extract dropdown.
    identifier is the exact "provider/model" string passed as
    model_used. See backend/app/routers/models.py."""

    __tablename__ = "model_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier = Column(String(100), unique=True, nullable=False)
    provider = Column(String(20), nullable=False)
    display_name = Column(String(150), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VocabTerm(Base):
    """NEW (2026-09-01): admin-manageable, agent-grown catalogue of
    task_type and evaluation_metric terms actually seen across
    catalogued benchmarks. Serves two purposes:

    1. Guidance, not enforcement: agent_runner.py fetches the active,
       canonical terms per category and injects them into the
       extraction prompt as a REFERENCE sample (for spelling/naming
       consistency), not a closed enum -- Benchmark.task_type and
       Benchmark.evaluation_metrics remain free ARRAY(Text) columns,
       since evaluation metric names must match each paper's own
       terminology exactly (see BenchmarkForm.tsx's existing
       comma-separated tag input decision) and task types occasionally
       need a genuinely new value for a novel benchmark.
    2. Growth: after every successful extraction, agent_runner.py
       upserts each task_type/evaluation_metric value into this table
       (incrementing usage_count on repeats), so the reference list
       improves automatically as the catalogue grows, without a
       separate manual curation step required before it's useful.

    category: 'task_type' | 'evaluation_metric'.
    normalized_term: lowercased/punctuation-stripped form (same
    normalization as agent_runner.py's _normalize_metric_name()), used
    for the uniqueness constraint so trivial casing/punctuation
    differences don't create duplicate rows.
    is_canonical / canonical_term_id: lets an admin mark a term as an
    alias of another (e.g. "ASR" -> "Attack Success Rate") via the CRUD
    UI, without deleting the alias outright (so historical searches for
    either spelling still resolve to the same concept).
    source: 'agent' (auto-upserted from an extraction) or 'admin'
    (manually added/edited), so the CRUD UI can filter to
    recently-agent-added, unreviewed terms.
    """

    __tablename__ = "vocab_terms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(20), nullable=False)
    term = Column(String(255), nullable=False)
    normalized_term = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_canonical = Column(Boolean, nullable=False, default=True)
    canonical_term_id = Column(UUID(as_uuid=True), ForeignKey("vocab_terms.id"), nullable=True)
    first_seen_benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="SET NULL"), nullable=True)
    usage_count = Column(Integer, nullable=False, default=1)
    source = Column(String(20), nullable=False, default="agent")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_name = Column(String(100), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(20), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    diff = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
