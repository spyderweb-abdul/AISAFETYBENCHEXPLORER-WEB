from app.core.catalogue_summary import build_catalogue_summary


def test_catalogue_summary_aggregates_published_row_values():
    rows = [
        ("Popular", ["Accuracy", "F1"], 120, "https://code.test/a", "https://data.test/a"),
        ("High", ["ASR"], 30, "https://code.test/b", None),
        ("Medium", [], 0, None, "https://data.test/c"),
        ("Low", ["Pass rate"], 10, "https://code.test/d", "https://data.test/d"),
    ]

    summary = build_catalogue_summary(rows)

    assert summary["total_benchmarks"] == 4
    assert summary["popular"] == 1
    assert summary["high"] == 1
    assert summary["medium"] == 1
    assert summary["average_metrics_per_benchmark"] == 1.0
    assert summary["average_citations"] == 40.0
    assert summary["code_and_data_coverage_percent"] == 50.0


def test_catalogue_summary_handles_an_empty_catalogue():
    summary = build_catalogue_summary([])

    assert summary["total_benchmarks"] == 0
    assert summary["popular"] == 0
    assert summary["high"] == 0
    assert summary["medium"] == 0
    assert summary["average_metrics_per_benchmark"] == 0.0
    assert summary["average_citations"] == 0.0
    assert summary["code_and_data_coverage_percent"] == 0.0
