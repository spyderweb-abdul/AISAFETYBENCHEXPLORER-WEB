"""
app/routers/stats.py

Phase 5: public (no auth required, matching GET /benchmarks) endpoint
for the Research Gap Heatmap. Aggregates over published benchmarks'
safety_dimensions x complexity_level, replicating
research_gap_heatmap.py's exact severity rules (see
app/core/safety_dimension_classifier.py's calculate_gap_severity()).

Computed live in Python rather than as a materialized SQL view (Section
4's original schema-mapping table named a materialized view for this),
since the catalogue is small (182+ benchmarks per Section 1) and this
avoids introducing PostgreSQL array-unnest aggregation SQL that would be
harder to keep in sync with the deterministic classifier module if its
category list ever changes. Revisit as a materialized view if the
catalogue grows large enough for this to become a real cost.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.safety_dimension_classifier import build_research_gap_heatmap
from app.db.session import get_db
from app.models.orm import Benchmark
from app.schemas.stats import ResearchGapHeatmapOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/research-gap-heatmap", response_model=ResearchGapHeatmapOut)
def get_research_gap_heatmap(db: Session = Depends(get_db)):
    rows = (
        db.query(Benchmark.safety_dimensions, Benchmark.complexity_level)
        .filter(Benchmark.status == "published")
        .all()
    )
    dimensions = build_research_gap_heatmap([(r[0], r[1]) for r in rows])
    return ResearchGapHeatmapOut(total_benchmarks=len(rows), dimensions=dimensions)
