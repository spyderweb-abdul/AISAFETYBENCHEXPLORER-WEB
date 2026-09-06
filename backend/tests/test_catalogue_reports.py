from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.core.catalogue_reports import build_catalogue_reports


def benchmark(identifier: str, **overrides):
    values = {
        "id": identifier,
        "benchmark_name": f"Benchmark {identifier}",
        "release_date": date(2024, 1, 1),
        "complexity_level": "Medium",
        "task_type": [],
        "evaluation_metrics": [],
        "cited_by": 0,
        "language_support": [],
        "entry_modalities": [],
        "license": None,
        "created_by": None,
        "dev_purpose": None,
        "use_cases": [],
        "safety_dimensions": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def repo_stat(benchmark_id: str, source: str, **overrides):
    values = {
        "benchmark_id": benchmark_id,
        "source": source,
        "activity_status": "active",
        "stars_or_likes": 0,
        "fetched_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_catalogue_reports_aggregate_multivalue_metadata_once_per_benchmark():
    rows = [
        benchmark(
            "a",
            benchmark_name="Alpha",
            release_date=date(2023, 1, 1),
            complexity_level="Popular",
            task_type=["Jailbreak", "jailbreak", "Toxicity"],
            evaluation_metrics=["Accuracy"],
            cited_by=120,
            language_support=["English"],
            entry_modalities=["Text"],
            license="MIT",
            created_by="Human",
            dev_purpose="Eval",
            use_cases=["Model evaluation"],
            safety_dimensions=["Jailbreak & Adversarial"],
        ),
        benchmark(
            "b",
            benchmark_name="Beta",
            complexity_level="High",
            task_type=["JAILBREAK"],
            evaluation_metrics=["F1"],
            cited_by=40,
            language_support=["English", "French"],
            entry_modalities=["Text"],
            license="Apache-2.0",
            created_by="Hybrid",
            dev_purpose="Train & Eval",
            use_cases=["Model evaluation", "Research"],
            safety_dimensions=["Jailbreak & Adversarial"],
        ),
    ]

    report = build_catalogue_reports(rows, [])

    assert report["total_benchmarks"] == 2
    assert report["publication_trend"] == [
        {"year": 2023, "count": 1, "year_over_year_percent": None},
        {"year": 2024, "count": 1, "year_over_year_percent": 0.0},
    ]
    assert report["task_types"][0] == {
        "label": "Jailbreak",
        "count": 2,
        "share_percent": 100.0,
    }
    assert report["citation_leaders"][0]["benchmark_name"] == "Alpha"
    assert report["creation_methodology"][0]["label"] in {"Human-authored", "Hybrid"}
    assert report["research_gaps"][1]["popular"] == 1
    assert report["research_gaps"][1]["high"] == 1


def test_catalogue_reports_use_latest_ordered_repository_snapshots():
    rows = [benchmark("a"), benchmark("b")]
    stats = [
        repo_stat("a", "github", activity_status="stale", stars_or_likes=520),
        repo_stat("a", "github", activity_status="active", stars_or_likes=20),
        repo_stat("a", "hf_dataset", activity_status="slowing"),
    ]

    report = build_catalogue_reports(rows, stats)

    stale = next(row for row in report["repository_health"] if row["status"] == "Stale")
    slowing = next(row for row in report["repository_health"] if row["status"] == "Slowing")
    unknown = next(row for row in report["repository_health"] if row["status"] == "Unknown")
    star_band = next(row for row in report["github_star_distribution"] if row["label"] == "500-999")
    assert stale["github"] == 1
    assert slowing["hugging_face"] == 1
    assert unknown == {"status": "Unknown", "github": 1, "hugging_face": 1}
    assert star_band["count"] == 1


def test_catalogue_reports_handle_an_empty_catalogue():
    report = build_catalogue_reports([], [])

    assert report["total_benchmarks"] == 0
    assert report["publication_trend"] == []
    assert report["task_types"] == []
    assert all(row["count"] == 0 for row in report["complexity_distribution"])


def test_language_report_uses_full_names_for_legacy_codes():
    report = build_catalogue_reports(
        [
            benchmark("a", language_support=["en"]),
            benchmark("b", language_support=["English"]),
        ],
        [],
    )

    assert report["language_coverage"] == [
        {"label": "English", "count": 2, "share_percent": 100.0},
    ]


def test_publication_trend_includes_zero_count_years():
    report = build_catalogue_reports(
        [
            benchmark("a", release_date=date(2021, 1, 1)),
            benchmark("b", release_date=date(2023, 1, 1)),
        ],
        [],
    )

    assert report["publication_trend"] == [
        {"year": 2021, "count": 1, "year_over_year_percent": None},
        {"year": 2022, "count": 0, "year_over_year_percent": -100.0},
        {"year": 2023, "count": 1, "year_over_year_percent": None},
    ]
