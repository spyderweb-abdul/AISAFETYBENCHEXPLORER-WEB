"""
app/routers/repo_stats.py

New admin router for Phase 4 manual/bulk scraper triggers.
Follows the same require_admin + audit-log pattern used in
benchmarks.py and extraction.py.

Register in app/main.py:
    from app.routers import repo_stats
    app.include_router(repo_stats.router)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import require_admin
from app.core.tasks import refresh_all_repo_stats, refresh_repo_stats_for_benchmark
from app.db.session import get_db
from app.models.orm import Benchmark, RepoStat
from app.schemas.repo_stats import RepoStatsOut

router = APIRouter(prefix="/repo-stats", tags=["repo-stats"])


@router.get("/benchmarks/{benchmark_id}", response_model=list[RepoStatsOut])
def get_repo_stats_for_benchmark(
    benchmark_id: UUID,
    db: Session = Depends(get_db),
):
    rows = db.query(RepoStats).filter(RepoStats.benchmark_id == benchmark_id).all()
    return rows


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
