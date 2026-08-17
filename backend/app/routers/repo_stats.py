"""
app/routers/repo_stats.py

Admin router for Phase 4 manual/bulk scraper triggers (roadmap item 13)
and repo_stats history / GitHub quota visibility (roadmap items 14/15).
Follows the same require_admin + audit-log pattern used in benchmarks.py
and extraction.py. Registered in app/main.py.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.config import settings
from app.core.deps import require_admin
from app.core.github_rate_limit import check_github_rate_limit
from app.core.tasks import refresh_all_repo_stats, refresh_repo_stats_for_benchmark
from app.db.session import get_db
from app.models.orm import Benchmark, RepoStat
from app.schemas.repo_stats import RepoStatsOut

router = APIRouter(prefix="/repo-stats", tags=["repo-stats"])


@router.get("/benchmarks/{benchmark_id}", response_model=list[RepoStatsOut])
def get_repo_stats_for_benchmark(
    benchmark_id: UUID,
    history: bool = Query(
        False,
        description=(
            "Roadmap item 15: repo_stats is now an append-only history "
            "table (see app/core/tasks.py's _insert_repo_stats_snapshot). "
            "By default this returns only the latest row per source, "
            "matching the previous one-row-per-source behavior admins "
            "already expect on the benchmark edit page. Pass "
            "history=true to get every historical snapshot instead."
        ),
    ),
    db: Session = Depends(get_db),
):
    if history:
        rows = (
            db.query(RepoStat)
            .filter(RepoStat.benchmark_id == benchmark_id)
            .order_by(RepoStat.source, RepoStat.fetched_at.desc())
            .all()
        )
        return rows

    latest_per_source = (
        db.query(RepoStat.source, func.max(RepoStat.fetched_at).label("max_fetched_at"))
        .filter(RepoStat.benchmark_id == benchmark_id)
        .group_by(RepoStat.source)
        .subquery()
    )
    rows = (
        db.query(RepoStat)
        .join(
            latest_per_source,
            (RepoStat.source == latest_per_source.c.source)
            & (RepoStat.fetched_at == latest_per_source.c.max_fetched_at),
        )
        .filter(RepoStat.benchmark_id == benchmark_id)
        .order_by(RepoStat.source)
        .all()
    )
    return rows


@router.get("/github-rate-limit")
def get_github_rate_limit(
    _: object = Depends(require_admin),
) -> dict:
    """Roadmap item 14: on-demand visibility into remaining GitHub API
    quota, so headroom can be checked before a large bulk refresh
    instead of only discovering exhaustion via scattered 403 errors
    after the fact. refresh_all_repo_stats() already checks this
    automatically before queuing; this endpoint is for a human to check
    proactively at any time."""
    return check_github_rate_limit(settings.GITHUB_TOKEN)


@router.post("/benchmarks/{benchmark_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def trigger_refresh_for_benchmark(
    benchmark_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    task = refresh_repo_stats_for_benchmark.delay(str(benchmark_id))

    log_action(
        db, table_name="repo_stats", record_id=benchmark_id, action="refresh_triggered",
        changed_by=current_user.id, diff={"celery_task_id": task.id},
    )
    db.commit()

    return {"task_id": task.id, "benchmark_id": str(benchmark_id)}


@router.post("/refresh-all", status_code=status.HTTP_202_ACCEPTED)
def trigger_refresh_all(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    task = refresh_all_repo_stats.delay()

    log_action(
        db, table_name="repo_stats", record_id=None, action="bulk_refresh_triggered",
        changed_by=current_user.id, diff={"celery_task_id": task.id},
    )
    db.commit()

    return {"task_id": task.id}
