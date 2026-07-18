from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EvalMetricBase(BaseModel):
    benchmark_name: str
    paper_title: str
    paper_link: str | None = None
    metric_name: str
    conceptual_description: str | None = None
    methodological_details: str | None = None
    mathematical_definition: str | None = None
    differences_from_standard_definition: str | None = None
    notes: str | None = None


class EvalMetricCreate(EvalMetricBase):
    benchmark_id: UUID


class EvalMetricUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_name: str | None = None
    paper_title: str | None = None
    paper_link: str | None = None
    metric_name: str | None = None
    conceptual_description: str | None = None
    methodological_details: str | None = None
    mathematical_definition: str | None = None
    differences_from_standard_definition: str | None = None
    notes: str | None = None


class EvalMetricOut(EvalMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    benchmark_id: UUID
    created_at: datetime
    updated_at: datetime


class MetricsCompleteness(BaseModel):
    """Flags Sheet 1 <-> Sheet 2 consistency: metric names listed on the
    benchmark's evaluation_metrics field that have no corresponding
    eval_metrics catalogue row yet.
    Mirrors the check already enforced server-side during agent extraction
    (agent_runner.py), surfaced here for human reviewers editing a
    benchmark manually in the CRUD UI.
    """
    benchmark_id: UUID
    missing_metric_names: list[str]
    is_complete: bool
