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
    submitted_by: Optional[uuid.UUID]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ExtractionJobReview(BaseModel):
    approve: bool
    reviewer_note: Optional[str] = None
