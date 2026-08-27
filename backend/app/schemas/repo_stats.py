from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RepoStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    benchmark_id: UUID
    source: str
    url: str
    owner: Optional[str] = None
    name: Optional[str] = None
    stars_or_likes: Optional[int] = None
    forks: Optional[int] = None
    open_issues: Optional[int] = None
    contributors_count: Optional[int] = None
    downloads: Optional[int] = None
    last_commit_at: Optional[datetime] = None
    days_since_last_activity: Optional[int] = None
    activity_status: Optional[str] = None
    is_archived: bool
    is_private: bool
    is_gated: bool
    license_id: Optional[str] = None
    fetch_error: Optional[str] = None
    fetched_at: datetime
