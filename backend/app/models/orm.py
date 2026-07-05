import uuid

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
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    metrics = relationship("EvalMetric", back_populates="benchmark", cascade="all, delete-orphan")
    repo_stats = relationship("RepoStat", back_populates="benchmark", cascade="all, delete-orphan")


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
    stars_or_likes = Column(Integer, default=0)
    last_commit_at = Column(DateTime(timezone=True))
    activity_status = Column(String(30))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    benchmark = relationship("Benchmark", back_populates="repo_stats")


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(20), nullable=False)
    source_value = Column(Text, nullable=False)
    model_used = Column(String(100))
    status = Column(job_status_enum, nullable=False, default="queued")
    quality_score = Column(Numeric(3, 2))
    requires_review = Column(Boolean, default=True)
    result_benchmark_id = Column(UUID(as_uuid=True), ForeignKey("benchmarks.id"))
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_name = Column(String(100), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(20), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    diff = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
