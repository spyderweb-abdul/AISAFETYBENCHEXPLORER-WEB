# Destination path: backend/app/schemas/vocab_term.py
# New file.

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_CATEGORIES = {"task_type", "evaluation_metric"}


class VocabTermBase(BaseModel):
    category: str = Field(..., description=f"One of: {sorted(ALLOWED_CATEGORIES)}")
    term: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    is_canonical: bool = True
    canonical_term_id: Optional[uuid.UUID] = None

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(ALLOWED_CATEGORIES)}")
        return v


class VocabTermCreate(VocabTermBase):
    pass


class VocabTermUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    is_canonical: Optional[bool] = None
    canonical_term_id: Optional[uuid.UUID] = None


class VocabTermOut(VocabTermBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    normalized_term: str
    usage_count: int
    source: str
    first_seen_benchmark_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime