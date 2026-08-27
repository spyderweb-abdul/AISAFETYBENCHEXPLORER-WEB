# Destination path: backend/app/schemas/submission.py
# New file.

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SubmissionCreate(BaseModel):
    """Community submissions are restricted to DOI only (not arXiv ID
    or raw PDF URL, unlike the admin Agent Extraction Panel) -- a DOI
    is the most reliably resolvable, spoof-resistant identifier, and
    keeps the surface area for the public-facing endpoint smaller."""
    source_value: str = Field(..., min_length=5, max_length=500, description="A DOI, e.g. 10.1073/pnas.2416228122")


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submitter_user_id: uuid.UUID
    source_type: str
    source_value: str
    model_used: str
    status: str
    extraction_job_id: Optional[uuid.UUID] = None
    result_benchmark_id: Optional[uuid.UUID] = None
    domain_check_passed: Optional[bool] = None
    domain_check_reason: Optional[str] = None
    quality_score: Optional[Decimal] = None
    admin_reviewer_id: Optional[uuid.UUID] = None
    admin_review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None


class SubmissionReview(BaseModel):
    """Admin decision on a pending_review submission.
    decision: "approve" | "reject" | "needs_better_extraction"
    reviewer_notes is REQUIRED for reject and needs_better_extraction
    (the submitter sees this verbatim), optional for approve."""
    decision: str = Field(..., pattern="^(approve|reject|needs_better_extraction)$")
    reviewer_notes: Optional[str] = Field(None, max_length=2000)


class SubmissionReextract(BaseModel):
    """Admin-triggered re-extraction of a needs_better_extraction
    submission, using a paid model of the admin's choosing (e.g.
    openai/gpt-4o or anthropic/claude-3-5-sonnet-20241022) -- the
    community-submission model restriction does not apply here, since
    this is an explicit, budget-aware admin action, not an open
    public-facing one."""
    model_used: str = Field(..., description="e.g. openai/gpt-4o or anthropic/claude-3-5-sonnet-20241022")
