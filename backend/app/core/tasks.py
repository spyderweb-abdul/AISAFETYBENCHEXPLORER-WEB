"""
app/core/tasks.py

Celery tasks wrapping github_scrapper.py and hf_scrapper.py.
New file -- place at app/core/tasks.py.

Provides:
- refresh_repo_stats_for_benchmark(benchmark_id): manual/single trigger
- refresh_all_repo_stats(): scheduled bulk trigger (Celery Beat, weekly)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.github_scrapper import fetch_github_stats
from app.core.hf_scrapper import fetch_hf_dataset_stats, fetch_hf_model_stats
from app.db.session import SessionLocal
from app.models.orm import Benchmark, RepoStat

logger = logging.getLogger(__name__)


def _upsert_repo_stats(db, benchmark_id, source: str, stats) -> None:
    existing = (
        db.query(RepoStat)
        .filter(RepoStat.benchmark_id == benchmark_id, RepoStat.source == source)
        .first()
    )
    
    fields = dict(
        owner=getattr(stats, "owner", None),
        name=getattr(stats, "name", None),
        forks=getattr(stats, "forks", None),
        open_issues=getattr(stats, "open_issues", None),
        contributors_count=getattr(stats, "contributors_count", None),
        stars_or_likes=getattr(stats, "stars", None) if getattr(stats, "stars", None) is not None else getattr(stats, "likes", None),
        downloads=getattr(stats, "downloads", None),
        last_commit_at=getattr(stats, "last_commit_at", None) or getattr(stats, "last_modified_at", None),
        days_since_last_activity=getattr(stats, "days_since_last_commit", None)
        or getattr(stats, "days_since_last_modified", None),
        activity_status=stats.activity_status,
        is_archived=getattr(stats, "is_archived", False),
        is_private=getattr(stats, "is_private", False),
        is_gated=getattr(stats, "is_gated", False),
        license_id=getattr(stats, "license_spdx", None) or getattr(stats, "license_id", None),
        fetch_error=stats.error,
        fetched_at=stats.fetched_at,
    )

    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
    else:
        db.add(RepoStat(id=uuid.uuid4(), benchmark_id=benchmark_id, source=source, **fields))


@celery_app.task(name="app.core.tasks.refresh_repo_stats_for_benchmark", bind=True, max_retries=2)
def refresh_repo_stats_for_benchmark(self, benchmark_id: str) -> dict:
    """
    Manual/single-benchmark trigger. Call from the admin API
    (see app/routers/repo_stats.py) or directly for testing.
    """
    db = SessionLocal()
    result = {"benchmark_id": benchmark_id, "sources_updated": []}
    try:
        benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if benchmark is None:
            logger.warning("refresh_repo_stats_for_benchmark: benchmark %s not found", benchmark_id)
            return {"benchmark_id": benchmark_id, "error": "benchmark_not_found"}

        if benchmark.code_repository:
            gh_stats = fetch_github_stats(benchmark.code_repository, github_token=settings.GITHUB_TOKEN)
            _upsert_repo_stats(db, benchmark.id, "github", gh_stats)
            result["sources_updated"].append("github")

        if benchmark.dataset_repository:
            hf_stats = fetch_hf_dataset_stats(benchmark.dataset_repository, hf_token=settings.HF_TOKEN)
            _upsert_repo_stats(db, benchmark.id, "hf_dataset", hf_stats)
            result["sources_updated"].append("hf_dataset")

        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        logger.error("refresh_repo_stats_for_benchmark failed for %s: %s", benchmark_id, exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="app.core.tasks.refresh_all_repo_stats")
def refresh_all_repo_stats() -> dict:
    """
    Scheduled bulk trigger, run weekly via Celery Beat (see celery_app.py).
    Also exposed for a manual "Refresh All" admin action.
    """
    db = SessionLocal()
    try:
        benchmark_ids = [str(b.id) for b in db.query(Benchmark.id).all()]
    finally:
        db.close()

    logger.info("refresh_all_repo_stats: queuing refresh for %d benchmarks", len(benchmark_ids))
    for benchmark_id in benchmark_ids:
        refresh_repo_stats_for_benchmark.delay(benchmark_id)

    return {"queued": len(benchmark_ids), "queued_at": datetime.now(timezone.utc).isoformat()}
