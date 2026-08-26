# Destination path: backend/app/core/tasks.py
# Replaces the existing file in full.
#
# CHANGES (Phase 6 item 1, this session): adds a weekly citation-count
# refresh, mirroring the exact Celery task pattern already proven for
# refresh_repo_stats_for_benchmark / refresh_all_repo_stats:
# - refresh_citation_count_for_benchmark(benchmark_id): manual/single
#   trigger, reuses paper_fetcher.py's existing
#   fetch_semantic_scholar_citation_count() (already used during
#   Phase 3 extraction, so this is not a new external integration).
# - refresh_all_citation_counts(): scheduled bulk trigger (Celery Beat,
#   weekly). Deliberately processes benchmarks SEQUENTIALLY within one
#   task rather than fanning out into N separate delayed tasks the way
#   refresh_all_repo_stats() does for GitHub/HuggingFace -- Semantic
#   Scholar's unauthenticated tier is limited to 1 request/second, and
#   fetch_semantic_scholar_citation_count() already retries internally
#   on 429s, so a small fixed delay between sequential calls is a
#   simpler and more predictable way to stay under that limit than
#   coordinating backoff across many concurrent Celery workers.
# - _apply_citation_refresh(): updates Benchmark.cited_by and, per the
#   roadmap's Phase 6 item 3 ask ("feeding the Popular classification
#   trigger automatically"), promotes complexity_level to "Popular"
#   if the new count crosses complexity_classifier.py's
#   POPULAR_CITATION_THRESHOLD (100) and the benchmark isn't already
#   Popular. This only uses the citation_count OR-branch of classify()'s
#   three Popular conditions -- the other two
#   (cited_as_baseline_in_3plus_papers, is_community_standard) and all
#   High/Medium signal booleans are not persisted on the Benchmark row
#   today (they only exist transiently in the admin form's classifier
#   UI), so a full re-classification is out of scope for an automated
#   citation-only refresh; this never demotes an existing
#   classification, only ever promotes to Popular when citation count
#   alone already justifies it.
# - Every actual change (citation count and/or complexity promotion)
#   is written to audit_log via the existing log_action() helper, with
#   changed_by=None to distinguish system-triggered changes from
#   human admin actions in the version history (see
#   VersionHistoryPanel.tsx).
# celery_app.py's Beat schedule (added in this same session) now also
# includes a weekly "refresh-all-citations-weekly" entry calling
# refresh_all_citation_counts. All existing repo_stats task code below
# is unchanged.

"""
app/core/tasks.py

Celery tasks wrapping github_scrapper.py and hf_scrapper.py, plus
(Phase 6) paper_fetcher.py's Semantic Scholar citation lookup.

Provides:
- refresh_repo_stats_for_benchmark(benchmark_id): manual/single trigger
- refresh_all_repo_stats(): scheduled bulk trigger (Celery Beat, weekly)
- refresh_citation_count_for_benchmark(benchmark_id): manual/single trigger
- refresh_all_citation_counts(): scheduled bulk trigger (Celery Beat, weekly)
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from app.core.audit import log_action
from app.core.celery_app import celery_app
from app.core.complexity_classifier import POPULAR_CITATION_THRESHOLD
from app.core.config import settings
from app.core.github_rate_limit import has_sufficient_quota
from app.core.github_scrapper import fetch_github_stats
from app.core.hf_scrapper import fetch_hf_dataset_stats, fetch_hf_model_stats
from app.core.paper_fetcher import fetch_semantic_scholar_citation_count
from app.db.session import SessionLocal
from app.models.orm import Benchmark, RepoStat

logger = logging.getLogger(__name__)

# Each fetch_github_stats() call makes 3 GitHub REST requests (per the
# Phase 4 section of PROJECT_ROADMAP.md). Used to estimate quota needed
# for a bulk refresh before queuing it.
_GITHUB_REQUESTS_PER_REPO = 3

# Stay comfortably under Semantic Scholar's unauthenticated 1 req/sec
# limit during a sequential bulk citation refresh. Not needed for the
# single-benchmark manual trigger, which only ever makes one call.
_SEMANTIC_SCHOLAR_DELAY_SECONDS = 1.1


def _insert_repo_stats_snapshot(db, benchmark_id, source: str, stats) -> None:
    """Roadmap item 15: always inserts a new RepoStat row rather than
    updating an existing one in place, so repo_stats accumulates a real
    history of fetched values over time instead of only ever holding
    the latest snapshot."""
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
            _insert_repo_stats_snapshot(db, benchmark.id, "github", gh_stats)
            result["sources_updated"].append("github")

        if benchmark.dataset_repository:
            hf_stats = fetch_hf_dataset_stats(benchmark.dataset_repository, hf_token=settings.HF_TOKEN)
            _insert_repo_stats_snapshot(db, benchmark.id, "hf_dataset", hf_stats)
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

    Roadmap item 14: checks GitHub's remaining rate-limit quota before
    queuing anything. Aborts early (queuing nothing) if there is not
    enough headroom for every benchmark with a code_repository, rather
    than queuing everything and letting most rows fail individually
    with "repo_fetch_failed: 403 rate limit exceeded" the way the
    original Phase 4 testing incident played out.
    """
    db = SessionLocal()
    try:
        benchmarks = db.query(Benchmark.id, Benchmark.code_repository).all()
    finally:
        db.close()

    benchmark_ids = [str(b.id) for b in benchmarks]
    github_repo_count = sum(1 for b in benchmarks if b.code_repository)
    estimated_github_requests = github_repo_count * _GITHUB_REQUESTS_PER_REPO

    if github_repo_count > 0:
        try:
            sufficient, quota_status = has_sufficient_quota(
                settings.GITHUB_TOKEN, estimated_github_requests
            )
        except Exception as exc:
            logger.warning(
                "refresh_all_repo_stats: could not check GitHub rate limit (%s) "
                "-- proceeding without a pre-flight guard.", exc,
            )
            sufficient, quota_status = True, None

        if not sufficient:
            logger.warning(
                "refresh_all_repo_stats: aborting -- estimated %d GitHub requests "
                "needed for %d repos, but only %s remain (resets at %s). Set "
                "GITHUB_TOKEN in backend/.env if this is running unauthenticated, "
                "or wait for the quota to reset, then retry.",
                estimated_github_requests, github_repo_count,
                quota_status["remaining"] if quota_status else "unknown",
                quota_status["reset_at"] if quota_status else "unknown",
            )
            return {
                "queued": 0,
                "skipped_due_to_rate_limit": True,
                "github_rate_limit_status": quota_status,
                "estimated_github_requests_needed": estimated_github_requests,
            }

    logger.info("refresh_all_repo_stats: queuing refresh for %d benchmarks", len(benchmark_ids))
    for benchmark_id in benchmark_ids:
        refresh_repo_stats_for_benchmark.delay(benchmark_id)

    return {"queued": len(benchmark_ids), "queued_at": datetime.now(timezone.utc).isoformat()}


def _citation_search_term(benchmark: Benchmark) -> str | None:
    """Best available search key for a Semantic Scholar lookup: prefer
    the paper_link (more precise, often a DOI or arXiv URL) and fall
    back to the paper title. Returns None if neither is available, so
    the caller can skip the benchmark rather than searching on an
    empty string."""
    if benchmark.paper_link:
        return benchmark.paper_link
    if benchmark.benchmark_paper_title:
        return benchmark.benchmark_paper_title
    return None


def _apply_citation_refresh(db, benchmark: Benchmark, new_count: int) -> bool:
    """Updates benchmark.cited_by and, if the new count now crosses
    POPULAR_CITATION_THRESHOLD, promotes complexity_level to "Popular".
    Never demotes an existing classification and never touches the
    other (unpersisted) complexity signals -- see the module docstring
    above for the full rationale. Returns True if the row actually
    changed, so the caller knows whether to write an audit_log entry.
    """
    before_cited_by = benchmark.cited_by
    before_complexity_level = benchmark.complexity_level

    benchmark.cited_by = new_count

    promoted = False
    if new_count > POPULAR_CITATION_THRESHOLD and benchmark.complexity_level != "Popular":
        benchmark.complexity_level = "Popular"
        benchmark.complexity_justification = (
            f"Popular -- citation count ({new_count}) exceeds "
            f"{POPULAR_CITATION_THRESHOLD} (auto-updated by the weekly "
            "citation refresh job)."
        )
        promoted = True

    changed = (new_count != before_cited_by) or promoted
    if changed:
        log_action(
            db, table_name="benchmarks", record_id=benchmark.id,
            action="citation_refresh_promoted_to_popular" if promoted else "citation_refresh",
            changed_by=None,
            diff={
                "before_cited_by": before_cited_by,
                "after_cited_by": new_count,
                "before_complexity_level": before_complexity_level,
                "after_complexity_level": benchmark.complexity_level,
            },
        )
    return changed


@celery_app.task(name="app.core.tasks.refresh_citation_count_for_benchmark", bind=True, max_retries=2)
def refresh_citation_count_for_benchmark(self, benchmark_id: str) -> dict:
    """Manual/single-benchmark trigger, mirroring
    refresh_repo_stats_for_benchmark's pattern. Call directly for
    testing, or wire up an admin "Refresh Citation Count" button later
    the same way repo_stats.py exposes refresh_repo_stats_for_benchmark."""
    db = SessionLocal()
    try:
        benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if benchmark is None:
            logger.warning("refresh_citation_count_for_benchmark: benchmark %s not found", benchmark_id)
            return {"benchmark_id": benchmark_id, "error": "benchmark_not_found"}

        search_term = _citation_search_term(benchmark)
        if not search_term:
            logger.info(
                "refresh_citation_count_for_benchmark: skipping %s -- no paper_link or paper title.",
                benchmark_id,
            )
            return {"benchmark_id": benchmark_id, "skipped": "no_search_term"}

        new_count = fetch_semantic_scholar_citation_count(
            search_term, api_key=settings.SEMANTIC_SCHOLAR_API_KEY
        )
        if new_count is None:
            logger.warning(
                "refresh_citation_count_for_benchmark: Semantic Scholar lookup failed for %s.",
                benchmark_id,
            )
            return {"benchmark_id": benchmark_id, "error": "citation_lookup_failed"}

        changed = _apply_citation_refresh(db, benchmark, new_count)
        db.commit()
        return {"benchmark_id": benchmark_id, "new_cited_by": new_count, "changed": changed}
    except Exception as exc:
        db.rollback()
        logger.error("refresh_citation_count_for_benchmark failed for %s: %s", benchmark_id, exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="app.core.tasks.refresh_all_citation_counts")
def refresh_all_citation_counts() -> dict:
    """Scheduled bulk trigger, run weekly via Celery Beat (see
    celery_app.py). Processes benchmarks sequentially within this one
    task -- see the module docstring above for why this deliberately
    does not fan out into per-benchmark delayed tasks the way
    refresh_all_repo_stats() does. Also exposed for a manual
    "Refresh All Citations" admin action later.
    """
    db = SessionLocal()
    try:
        benchmarks = (
            db.query(Benchmark)
            .filter(Benchmark.status != "rejected")
            .all()
        )
    finally:
        db.close()

    updated = 0
    skipped = 0
    failed = 0

    db = SessionLocal()
    try:
        for benchmark in benchmarks:
            search_term = _citation_search_term(benchmark)
            if not search_term:
                skipped += 1
                continue

            new_count = fetch_semantic_scholar_citation_count(
                search_term, api_key=settings.SEMANTIC_SCHOLAR_API_KEY
            )
            if new_count is None:
                failed += 1
                time.sleep(_SEMANTIC_SCHOLAR_DELAY_SECONDS)
                continue

            if _apply_citation_refresh(db, benchmark, new_count):
                updated += 1
            time.sleep(_SEMANTIC_SCHOLAR_DELAY_SECONDS)

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("refresh_all_citation_counts failed mid-run: %s", exc)
        raise
    finally:
        db.close()

    logger.info(
        "refresh_all_citation_counts: processed %d benchmarks (updated=%d, skipped=%d, failed=%d).",
        len(benchmarks), updated, skipped, failed,
    )
    return {"processed": len(benchmarks), "updated": updated, "skipped": skipped, "failed": failed}
