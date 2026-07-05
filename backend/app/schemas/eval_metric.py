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


class EvalMetricOut(EvalMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    benchmark_id: UUID
    created_at: datetime
    updated_at: datetime
