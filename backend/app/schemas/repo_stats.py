"""
app/schemas/repo_stats.py

New Pydantic schema for the RepoStats ORM model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RepoStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    benchmark_id: Optional[UUID]
    source: str
    owner: Optional[str]
    name: Optional[str]
    stars: Optional[int]
    forks: Optional[int]
    open_issues: Optional[int]
    contributors_count: Optional[int]
    likes: Optional[int]
    downloads: Optional[int]
    last_activity_at: Optional[datetime]
    days_since_last_activity: Optional[int]
    activity_status: str
    is_archived: bool
    is_private: bool
    is_gated: bool
    license_id: Optional[str]
    fetch_error: Optional[str]
    fetched_at: datetime
