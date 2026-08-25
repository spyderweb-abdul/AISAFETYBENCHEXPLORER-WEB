"""
app/schemas/stats.py

Phase 5: Research Gap Heatmap response schema. See
app/core/safety_dimension_classifier.py's build_research_gap_heatmap()
for the aggregation logic and app/routers/stats.py for the endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel


class HeatmapDimension(BaseModel):
    dimension: str
    popular: int
    high: int
    medium: int
    low: int
    total: int
    gap_severity: str


class ResearchGapHeatmapOut(BaseModel):
    total_benchmarks: int
    dimensions: list[HeatmapDimension]
