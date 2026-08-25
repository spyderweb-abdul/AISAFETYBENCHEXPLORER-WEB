"""
app/scripts/backfill_use_case_safety_dimensions.py

Phase 5: computes use_cases and safety_dimensions for every existing
benchmark that predates this feature, matching the precedent set by
app/scripts/backfill_repo_stats.py for Phase 4.

Unlike that script, this one is safe to re-run unconditionally (not
just idempotent/skip-if-exists) -- both classifiers are pure functions
of task_type/description/benchmark_name, so recomputing and overwriting
is always correct, never destructive. Run this again any time the
classifier keyword lists change, to refresh existing rows.

Usage:
    docker compose exec backend python -m app.scripts.backfill_use_case_safety_dimensions
    docker compose exec backend python -m app.scripts.backfill_use_case_safety_dimensions --dry-run
    docker compose exec backend python -m app.scripts.backfill_use_case_safety_dimensions --limit 10
"""

from __future__ import annotations

import argparse
import logging

from app.core.safety_dimension_classifier import classify_safety_dimensions
from app.core.use_case_classifier import classify_use_cases
from app.db.session import SessionLocal
from app.models.orm import Benchmark

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(dry_run: bool = False, limit: int | None = None) -> None:
    db = SessionLocal()
    try:
        query = db.query(Benchmark).order_by(Benchmark.benchmark_name)
        if limit:
            query = query.limit(limit)
        benchmarks = query.all()

        logger.info("Backfilling use_cases/safety_dimensions for %d benchmark(s)%s.",
                    len(benchmarks), " (dry run)" if dry_run else "")

        updated = 0
        for benchmark in benchmarks:
            new_use_cases = classify_use_cases(
                benchmark.task_type, benchmark.description, benchmark.benchmark_name
            )
            new_safety_dimensions = classify_safety_dimensions(benchmark.task_type)

            changed = (
                new_use_cases != (benchmark.use_cases or [])
                or new_safety_dimensions != (benchmark.safety_dimensions or [])
            )
            if changed:
                logger.info(
                    "%s: use_cases %s -> %s, safety_dimensions %s -> %s",
                    benchmark.benchmark_name,
                    benchmark.use_cases, new_use_cases,
                    benchmark.safety_dimensions, new_safety_dimensions,
                )
                if not dry_run:
                    benchmark.use_cases = new_use_cases
                    benchmark.safety_dimensions = new_safety_dimensions
                updated += 1

        if dry_run:
            logger.info("Dry run complete. %d of %d row(s) would change.", updated, len(benchmarks))
            db.rollback()
        else:
            db.commit()
            logger.info("Backfill complete. %d of %d row(s) updated.", updated, len(benchmarks))
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    main(dry_run=args.dry_run, limit=args.limit)
