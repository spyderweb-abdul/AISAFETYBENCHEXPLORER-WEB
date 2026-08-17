"""
app/schemas/repo_stats.py

Pydantic output schema for the RepoStat ORM model (app/models/orm.py).

Fix (roadmap item 13): the previous version of this file declared fields
that do not exist on the RepoStat model at all (stars, likes,
last_activity_at). RepoStat stores a single combined stars_or_likes
column and last_commit_at, not last_activity_at. Because RepoStatsOut
used from_attributes=True, Pydantic would try to read .stars, .likes,
and .last_activity_at directly off a RepoStat instance and raise a
validation error on every GET /repo-stats/benchmarks/{id} call.
benchmark_id and url are also NOT NULL on the model, so they are typed
as required here instead of Optional.
"""

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
