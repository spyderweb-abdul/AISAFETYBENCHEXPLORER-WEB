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


class CatalogueSummaryOut(BaseModel):
    total_benchmarks: int
    popular: int
    high: int
    medium: int
    average_metrics_per_benchmark: float
    average_citations: float
    code_and_data_coverage_percent: float


class CategoryCount(BaseModel):
    label: str
    count: int
    share_percent: float


class PublicationYear(BaseModel):
    year: int
    count: int
    year_over_year_percent: float | None


class CitationLeader(BaseModel):
    benchmark_id: str
    benchmark_name: str
    citations: int
    complexity_level: str


class RepositoryHealth(BaseModel):
    status: str
    github: int
    hugging_face: int


class CatalogueReportsOut(BaseModel):
    total_benchmarks: int
    undated_benchmarks: int
    publication_trend: list[PublicationYear]
    complexity_distribution: list[CategoryCount]
    task_types: list[CategoryCount]
    evaluation_metrics: list[CategoryCount]
    citation_leaders: list[CitationLeader]
    repository_health: list[RepositoryHealth]
    github_star_distribution: list[CategoryCount]
    language_coverage: list[CategoryCount]
    modality_coverage: list[CategoryCount]
    license_distribution: list[CategoryCount]
    creation_methodology: list[CategoryCount]
    development_purpose: list[CategoryCount]
    use_case_distribution: list[CategoryCount]
    research_gaps: list[HeatmapDimension]
