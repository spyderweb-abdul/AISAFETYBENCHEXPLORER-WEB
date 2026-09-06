from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaperMetadataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    benchmark_id: UUID
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    semantic_scholar_paper_id: Optional[str] = None
    canonical_title: Optional[str] = None
    authors: Optional[str] = None
    venue: Optional[str] = None
    publication_date: Optional[date] = None
    is_open_access: Optional[bool] = None
    open_access_url: Optional[str] = None
    metadata_source: Optional[str] = None
    citation_count: Optional[int] = None
    citation_source: Optional[str] = None
    citation_checked_at: Optional[datetime] = None
    last_refreshed_at: Optional[datetime] = None
    last_error: Optional[str] = None


class CitationSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    benchmark_id: UUID
    citation_count: int
    source: str
    fetched_at: datetime
