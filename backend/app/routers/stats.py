# Destination path: backend/app/routers/stats.py
# Replaces the existing file in full.
#
# CHANGES (Phase 5 gap closure, this session):
# GET /research-gap-heatmap is one of the public, unauthenticated
# endpoints named in Known Gap item 22. Added an explicit slowapi rate
# limit (20/minute, tighter than the 100/minute global default in
# app/core/rate_limit.py) since this endpoint aggregates over every
# published benchmark on each call rather than a simple filtered list
# query. No change to the heatmap computation itself.

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.catalogue_summary import build_catalogue_summary
from app.core.catalogue_reports import build_catalogue_reports
from app.core.rate_limit import limiter
from app.core.safety_dimension_classifier import build_research_gap_heatmap
from app.db.session import get_db
from app.models.orm import Benchmark, RepoStat
from app.schemas.stats import CatalogueReportsOut, CatalogueSummaryOut, ResearchGapHeatmapOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/catalogue-summary", response_model=CatalogueSummaryOut)
@limiter.limit("30/minute")
def get_catalogue_summary(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(
            Benchmark.complexity_level,
            Benchmark.evaluation_metrics,
            Benchmark.cited_by,
            Benchmark.code_repository,
            Benchmark.dataset_repository,
        )
        .filter(Benchmark.status == "published")
        .all()
    )
    return build_catalogue_summary(rows)


@router.get("/catalogue-reports", response_model=CatalogueReportsOut)
@limiter.limit("20/minute")
def get_catalogue_reports(request: Request, db: Session = Depends(get_db)):
    benchmarks = (
        db.query(
            Benchmark.id,
            Benchmark.benchmark_name,
            Benchmark.task_type,
            Benchmark.release_date,
            Benchmark.created_by,
            Benchmark.entry_modalities,
            Benchmark.dev_purpose,
            Benchmark.license,
            Benchmark.evaluation_metrics,
            Benchmark.complexity_level,
            Benchmark.language_support,
            Benchmark.cited_by,
            Benchmark.use_cases,
            Benchmark.safety_dimensions,
        )
        .filter(Benchmark.status == "published")
        .order_by(Benchmark.benchmark_name.asc(), Benchmark.id.asc())
        .all()
    )
    benchmark_ids = [benchmark.id for benchmark in benchmarks]
    repo_stats = []
    if benchmark_ids:
        repo_stats = (
            db.query(RepoStat)
            .filter(RepoStat.benchmark_id.in_(benchmark_ids))
            .order_by(RepoStat.fetched_at.desc().nullslast(), RepoStat.id.desc())
            .all()
        )
    return build_catalogue_reports(benchmarks, repo_stats)


@router.get("/research-gap-heatmap", response_model=ResearchGapHeatmapOut)
@limiter.limit("20/minute")
def get_research_gap_heatmap(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(Benchmark.safety_dimensions, Benchmark.complexity_level)
        .filter(Benchmark.status == "published")
        .all()
    )
    dimensions = build_research_gap_heatmap([(r[0], r[1]) for r in rows])
    return ResearchGapHeatmapOut(total_benchmarks=len(rows), dimensions=dimensions)
