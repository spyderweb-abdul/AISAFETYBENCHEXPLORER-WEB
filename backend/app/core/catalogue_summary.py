"""Aggregate the live public catalogue into executive summary figures."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def build_catalogue_summary(rows: Sequence[tuple[Any, ...]]) -> dict[str, int | float]:
    """Summarize published benchmark metadata without list pagination.

    Code and data coverage is intentionally strict: a benchmark counts as
    covered only when both repository links are present.
    """
    total = len(rows)
    complexity_counts = {"Popular": 0, "High": 0, "Medium": 0}
    metric_count = 0
    citation_count = 0
    code_and_data_count = 0

    for row in rows:
        (
            complexity_level,
            evaluation_metrics,
            cited_by,
            code_repository,
            dataset_repository,
        ) = row

        if complexity_level in complexity_counts:
            complexity_counts[complexity_level] += 1
        metric_count += len(evaluation_metrics or [])
        citation_count += max(cited_by or 0, 0)

        has_code = isinstance(code_repository, str) and bool(code_repository.strip())
        has_data = isinstance(dataset_repository, str) and bool(dataset_repository.strip())
        if has_code and has_data:
            code_and_data_count += 1

    if total == 0:
        return {
            "total_benchmarks": 0,
            "popular": 0,
            "high": 0,
            "medium": 0,
            "average_metrics_per_benchmark": 0.0,
            "average_citations": 0.0,
            "code_and_data_coverage_percent": 0.0,
        }

    return {
        "total_benchmarks": total,
        "popular": complexity_counts["Popular"],
        "high": complexity_counts["High"],
        "medium": complexity_counts["Medium"],
        "average_metrics_per_benchmark": round(metric_count / total, 1),
        "average_citations": round(citation_count / total, 1),
        "code_and_data_coverage_percent": round(code_and_data_count / total * 100, 1),
    }
