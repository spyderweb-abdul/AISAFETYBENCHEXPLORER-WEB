from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionJobCreate(BaseModel):
    source_type: str = Field(
        ...,
        description="One of: doi, arxiv_id, pdf_url",
        pattern="^(doi|arxiv_id|pdf_url)$",
    )
    source_value: str = Field(..., min_length=3, max_length=500)
    model_used: str = Field(
        default="openai/gpt-4o",
        description="Model identifier, e.g. openai/gpt-4o or anthropic/claude-3-5-sonnet-20241022",
    )


class ExtractionJobOut(BaseModel):
    id: uuid.UUID
    source_type: str
    source_value: str
    model_used: Optional[str]
    status: str
    quality_score: Optional[Decimal]
    requires_review: bool
    result_benchmark_id: Optional[uuid.UUID]
    # FIX (2026-08-23): job.status alone does not tell you whether the
    # resulting benchmark still needs human review -- a high
    # quality_score run gets job.status="done" immediately, even though
    # its benchmark is still Benchmark.status="pending_review" until an
    # admin actually approves it. Without this field, the admin frontend
    # had no way to show that benchmark in its Pending Review queue at
    # all, since that queue previously filtered on job.status ==
    # "needs_review" only. Populated via a join in
    # app/routers/extraction.py's list_jobs()/get_job(), not a real
    # column on ExtractionJob -- set as a plain attribute on the ORM
    # instance before Pydantic reads it via from_attributes.
    result_benchmark_status: Optional[str] = None
    submitted_by: Optional[uuid.UUID]
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[Decimal] = None
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ExtractionJobReview(BaseModel):
    approve: bool
    reviewer_note: Optional[str] = None


class JobVarianceOut(BaseModel):
    """Roadmap item 12: run-to-run variance for repeated extraction
    attempts against the same source_value (e.g. the PNAS job that was
    re-run 4 times during Phase 3 iteration, per PROJECT_ROADMAP.md's
    Change Log). Computed on read from existing ExtractionJob rows --
    no new table or column stores this directly."""

    source_value: str
    run_count: int
    mean_quality_score: Optional[float] = None
    stddev_quality_score: Optional[float] = None
    total_estimated_cost_usd: Optional[Decimal] = None
    job_ids: list[uuid.UUID] = Field(default_factory=list)
