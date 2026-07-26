"""Backfill script: populate RepoStat rows for benchmarks extracted before
Phase 4 shipped (i.e. before github_scrapper.py / hf_scrapper.py were wired
into agent_runner.py).

Context: as of 2026-07-26, only benchmarks extracted AFTER the Phase 4 patch
went live get their code_repository / dataset_repository verified against
the real GitHub / HuggingFace APIs and persisted as RepoStat rows. Every
benchmark extracted before that point (see ExtractionJob.completed_at <
2026-07-26) has a code_repository / dataset_repository string on the
Benchmark row itself, but no matching RepoStat row.

This script finds those benchmarks and runs them through the same scraper
functions agent_runner.py now uses live, then persists RepoStat rows the
same way. It is idempotent: it skips any benchmark that already has a
RepoStat row for a given source, so it is safe to re-run (e.g. as a cron
job or manually after fixing a scraper bug) without creating duplicates.

Usage:
    docker compose exec backend python -m app.scripts.backfill_repo_stats
    docker compose exec backend python -m app.scripts.backfill_repo_stats --dry-run
    docker compose exec backend python -m app.scripts.backfill_repo_stats --limit 20
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid

from app.core.config import settings
from app.core.github_scrapper import fetch_github_stats
from app.core.hf_scrapper import fetch_hf_dataset_stats
from app.db.session import SessionLocal
from app.models.orm import Benchmark, RepoStat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("backfill_repo_stats")

# Small delay between external API calls to stay well under GitHub's and
# HuggingFace's unauthenticated / low-tier rate limits when backfilling a
# large batch of benchmarks in one run.
_SLEEP_BETWEEN_CALLS_SECONDS = 1.0


def _has_existing_repo_stat(db, benchmark_id: uuid.UUID, source: str) -> bool:
    return (
        db.query(RepoStat)
        .filter(RepoStat.benchmark_id == benchmark_id, RepoStat.source == source)
        .first()
        is not None
    )


def _backfill_github(db, benchmark: Benchmark, dry_run: bool) -> str:
    if not benchmark.code_repository:
        return "skipped_no_url"
    if _has_existing_repo_stat(db, benchmark.id, "github"):
        return "skipped_exists"

    try:
        stats = fetch_github_stats(benchmark.code_repository, github_token=settings.GITHUB_TOKEN)
    except Exception as exc:
        logger.warning("Benchmark %s: github_scrapper raised %s", benchmark.benchmark_name, exc)
        return "error"

    if stats.error is not None:
        logger.warning(
            "Benchmark %s: GitHub verification failed for %s: %s",
            benchmark.benchmark_name, benchmark.code_repository, stats.error,
        )
        return "fetch_error"

    if dry_run:
        logger.info(
            "[dry-run] would insert github RepoStat for %s: stars=%d, license=%s, activity=%s",
            benchmark.benchmark_name, stats.stars, stats.license_spdx, stats.activity_status,
        )
        return "would_insert"

    db.add(RepoStat(
        id=uuid.uuid4(),
        benchmark_id=benchmark.id,
        source="github",
        url=benchmark.code_repository,
        owner=stats.owner,
        name=stats.repo,
        stars_or_likes=stats.stars,
        forks=stats.forks,
        open_issues=stats.open_issues,
        contributors_count=stats.contributors_count,
        last_commit_at=stats.last_commit_at,
        days_since_last_activity=stats.days_since_last_commit,
        activity_status=stats.activity_status,
        is_archived=stats.is_archived,
        license_id=stats.license_spdx,
        fetch_error=stats.error,
        fetched_at=stats.fetched_at,
    ))
    return "inserted"


def _backfill_hf(db, benchmark: Benchmark, dry_run: bool) -> str:
    if not benchmark.dataset_repository:
        return "skipped_no_url"
    if _has_existing_repo_stat(db, benchmark.id, "hf_dataset"):
        return "skipped_exists"

    try:
        stats = fetch_hf_dataset_stats(benchmark.dataset_repository, hf_token=settings.HF_TOKEN)
    except Exception as exc:
        logger.warning("Benchmark %s: hf_scrapper raised %s", benchmark.benchmark_name, exc)
        return "error"

    if stats.error is not None:
        logger.warning(
            "Benchmark %s: HuggingFace verification failed for %s: %s",
            benchmark.benchmark_name, benchmark.dataset_repository, stats.error,
        )
        return "fetch_error"

    if dry_run:
        logger.info(
            "[dry-run] would insert hf_dataset RepoStat for %s: likes=%d, license=%s, activity=%s",
            benchmark.benchmark_name, stats.likes, stats.license_id, stats.activity_status,
        )
        return "would_insert"

    db.add(RepoStat(
        id=uuid.uuid4(),
        benchmark_id=benchmark.id,
        source="hf_dataset",
        url=benchmark.dataset_repository,
        owner=stats.owner,
        name=stats.name,
        stars_or_likes=stats.likes,
        downloads=stats.downloads,
        last_commit_at=stats.last_modified_at,
        days_since_last_activity=stats.days_since_last_modified,
        activity_status=stats.activity_status,
        is_private=stats.is_private,
        is_gated=stats.is_gated,
        license_id=stats.license_id,
        fetch_error=stats.error,
        fetched_at=stats.fetched_at,
    ))
    return "inserted"


def run_backfill(limit: int | None, dry_run: bool) -> None:
    db = SessionLocal()
    counts = {
        "inserted": 0, "would_insert": 0, "skipped_no_url": 0,
        "skipped_exists": 0, "fetch_error": 0, "error": 0,
    }

    query = db.query(Benchmark).filter(
        (Benchmark.code_repository.isnot(None)) | (Benchmark.dataset_repository.isnot(None))
    ).order_by(Benchmark.created_at.asc())

    if limit:
        query = query.limit(limit)

    benchmarks = query.all()
    logger.info("Found %d benchmark(s) with a code or dataset repository to check.", len(benchmarks))

    for i, benchmark in enumerate(benchmarks, start=1):
        logger.info("[%d/%d] Processing %s", i, len(benchmarks), benchmark.benchmark_name)

        result_gh = _backfill_github(db, benchmark, dry_run)
        counts[result_gh] = counts.get(result_gh, 0) + 1
        if result_gh in ("inserted", "fetch_error", "error"):
            time.sleep(_SLEEP_BETWEEN_CALLS_SECONDS)

        result_hf = _backfill_hf(db, benchmark, dry_run)
        counts[result_hf] = counts.get(result_hf, 0) + 1
        if result_hf in ("inserted", "fetch_error", "error"):
            time.sleep(_SLEEP_BETWEEN_CALLS_SECONDS)

        if not dry_run and (result_gh == "inserted" or result_hf == "inserted"):
            db.commit()

    logger.info("Backfill complete. Summary: %s", counts)
    db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill RepoStat rows for pre-Phase-4 benchmarks.")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be inserted without writing to the DB.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N eligible benchmarks.")
    args = parser.parse_args()

    run_backfill(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
