"""Deterministic aggregations for the public catalogue report explorer.

The report endpoint deliberately works from all published benchmarks rather
than from the paginated browse response. Multi-valued metadata is counted at
most once per benchmark and grouped case-insensitively so small spelling-case
differences do not create duplicate report categories.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Iterable

from app.core.safety_dimension_classifier import build_research_gap_heatmap


COMPLEXITY_ORDER = ["Popular", "High", "Medium", "Low", "Unknown"]
REPOSITORY_STATUS_ORDER = ["Active", "Slowing", "Stale", "Archived", "Unknown"]
STAR_BANDS = ["0", "1-99", "100-499", "500-999", "1,000-4,999", "5,000+", "Unknown"]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _share(count: int, total: int) -> float:
    return round((count / total) * 100, 1) if total else 0.0


def _display_rank(value: str) -> tuple[int, str, str]:
    letters = "".join(character for character in value if character.isalpha())
    if letters and len(letters) <= 4 and letters.isupper():
        style_rank = 0
    elif letters and letters[:1].isupper() and any(character.islower() for character in letters):
        style_rank = 0
    elif letters and not (letters.islower() or letters.isupper()):
        style_rank = 1
    elif letters.islower():
        style_rank = 2
    else:
        style_rank = 3
    return style_rank, value.casefold(), value


def _category_rows(
    benchmarks: list[Any],
    attribute: str,
    *,
    total: int,
    limit: int | None = None,
    single_value: bool = False,
    label_map: dict[str, str] | None = None,
) -> list[dict]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}

    for benchmark in benchmarks:
        raw = getattr(benchmark, attribute, None)
        values = [raw] if single_value else (raw or [])
        seen: set[str] = set()
        for value in values:
            cleaned = _clean(value)
            if not cleaned:
                continue
            normalized = cleaned.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            candidate = (label_map or {}).get(cleaned, cleaned)
            if normalized not in display or _display_rank(candidate) < _display_rank(display[normalized]):
                display[normalized] = candidate
            counts[normalized] += 1

    ordered = sorted(counts, key=lambda key: (-counts[key], display[key].casefold()))
    if limit is not None:
        ordered = ordered[:limit]
    return [
        {
            "label": display[key],
            "count": counts[key],
            "share_percent": _share(counts[key], total),
        }
        for key in ordered
    ]


def _complexity_rows(benchmarks: list[Any], total: int) -> list[dict]:
    counts = Counter(_clean(getattr(row, "complexity_level", None)) or "Unknown" for row in benchmarks)
    return [
        {"label": level, "count": counts[level], "share_percent": _share(counts[level], total)}
        for level in COMPLEXITY_ORDER
    ]


def _publication_rows(benchmarks: list[Any]) -> tuple[list[dict], int]:
    counts: Counter[int] = Counter()
    undated = 0
    for benchmark in benchmarks:
        released = getattr(benchmark, "release_date", None)
        year: int | None = None
        if isinstance(released, date):
            year = released.year
        elif released:
            try:
                year = int(str(released)[:4])
            except (TypeError, ValueError):
                year = None
        if year is None:
            undated += 1
        else:
            counts[year] += 1

    rows = []
    previous: int | None = None
    for year in sorted(counts):
        count = counts[year]
        change = None if previous in (None, 0) else round(((count - previous) / previous) * 100, 1)
        rows.append({"year": year, "count": count, "year_over_year_percent": change})
        previous = count
    return rows, undated


def _citation_leaders(benchmarks: list[Any], limit: int = 15) -> list[dict]:
    ranked = sorted(
        benchmarks,
        key=lambda row: (
            -max(int(getattr(row, "cited_by", 0) or 0), 0),
            _clean(getattr(row, "benchmark_name", "")).casefold(),
        ),
    )[:limit]
    return [
        {
            "benchmark_id": str(getattr(row, "id", "")),
            "benchmark_name": _clean(getattr(row, "benchmark_name", "")) or "Unnamed benchmark",
            "citations": max(int(getattr(row, "cited_by", 0) or 0), 0),
            "complexity_level": _clean(getattr(row, "complexity_level", "")) or "Unknown",
        }
        for row in ranked
    ]


def _repository_source(value: Any) -> str | None:
    normalized = _clean(value).casefold()
    if normalized == "github":
        return "github"
    if normalized in {"hf", "hf_dataset", "huggingface", "hugging_face"}:
        return "hugging_face"
    return None


def _repository_status(value: Any) -> str:
    normalized = _clean(value).casefold()
    if normalized == "active":
        return "Active"
    if normalized == "slowing":
        return "Slowing"
    if normalized == "stale":
        return "Stale"
    if normalized == "archived":
        return "Archived"
    return "Unknown"


def _latest_repo_stats(repo_stats: Iterable[Any]) -> dict[tuple[str, str], Any]:
    latest: dict[tuple[str, str], Any] = {}
    for stat in repo_stats:
        source = _repository_source(getattr(stat, "source", None))
        if source is None:
            continue
        key = (str(getattr(stat, "benchmark_id", "")), source)
        if key not in latest:
            latest[key] = stat
    return latest


def _repository_reports(
    benchmarks: list[Any], repo_stats: Iterable[Any]
) -> tuple[list[dict], list[dict]]:
    latest = _latest_repo_stats(repo_stats)
    health = {
        status: {"github": 0, "hugging_face": 0}
        for status in REPOSITORY_STATUS_ORDER
    }
    stars: Counter[str] = Counter()

    for benchmark in benchmarks:
        benchmark_id = str(getattr(benchmark, "id", ""))
        for source in ("github", "hugging_face"):
            stat = latest.get((benchmark_id, source))
            status = _repository_status(getattr(stat, "activity_status", None)) if stat else "Unknown"
            health[status][source] += 1

        github_stat = latest.get((benchmark_id, "github"))
        raw_stars = getattr(github_stat, "stars_or_likes", None) if github_stat else None
        if raw_stars is None:
            band = "Unknown"
        else:
            value = max(int(raw_stars), 0)
            if value == 0:
                band = "0"
            elif value < 100:
                band = "1-99"
            elif value < 500:
                band = "100-499"
            elif value < 1_000:
                band = "500-999"
            elif value < 5_000:
                band = "1,000-4,999"
            else:
                band = "5,000+"
        stars[band] += 1

    health_rows = [
        {
            "status": status,
            "github": health[status]["github"],
            "hugging_face": health[status]["hugging_face"],
        }
        for status in REPOSITORY_STATUS_ORDER
    ]
    star_rows = [
        {
            "label": band,
            "count": stars[band],
            "share_percent": _share(stars[band], len(benchmarks)),
        }
        for band in STAR_BANDS
    ]
    return health_rows, star_rows


def build_catalogue_reports(benchmarks: Iterable[Any], repo_stats: Iterable[Any]) -> dict:
    """Build all live catalogue report tables from published records."""
    records = list(benchmarks)
    total = len(records)
    publication_trend, undated_count = _publication_rows(records)
    repository_health, github_star_distribution = _repository_reports(records, repo_stats)

    creation_labels = {
        "Human": "Human-authored",
        "Machine": "Machine-generated",
        "Hybrid": "Hybrid",
    }
    purpose_labels = {
        "Eval": "Evaluation only",
        "Train": "Training only",
        "Train & Eval": "Training and evaluation",
    }

    research_rows = [
        (getattr(row, "safety_dimensions", None) or [], getattr(row, "complexity_level", None))
        for row in records
    ]

    return {
        "total_benchmarks": total,
        "undated_benchmarks": undated_count,
        "publication_trend": publication_trend,
        "complexity_distribution": _complexity_rows(records, total),
        "task_types": _category_rows(records, "task_type", total=total, limit=20),
        "evaluation_metrics": _category_rows(records, "evaluation_metrics", total=total, limit=20),
        "citation_leaders": _citation_leaders(records),
        "repository_health": repository_health,
        "github_star_distribution": github_star_distribution,
        "language_coverage": _category_rows(records, "language_support", total=total, limit=20),
        "modality_coverage": _category_rows(records, "entry_modalities", total=total, limit=20),
        "license_distribution": _category_rows(
            records, "license", total=total, limit=20, single_value=True
        ),
        "creation_methodology": _category_rows(
            records,
            "created_by",
            total=total,
            single_value=True,
            label_map=creation_labels,
        ),
        "development_purpose": _category_rows(
            records,
            "dev_purpose",
            total=total,
            single_value=True,
            label_map=purpose_labels,
        ),
        "use_case_distribution": _category_rows(records, "use_cases", total=total),
        "research_gaps": build_research_gap_heatmap(research_rows),
    }
