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

from app.core.rate_limit import limiter
from app.core.safety_dimension_classifier import build_research_gap_heatmap
from app.db.session import get_db
from app.models.orm import Benchmark
from app.schemas.stats import ResearchGapHeatmapOut

router = APIRouter(prefix="/stats", tags=["stats"])


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
