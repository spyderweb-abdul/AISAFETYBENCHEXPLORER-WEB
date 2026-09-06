from app.core.languages import (
    LANGUAGE_SUPPORT,
    canonical_language_name,
    language_storage_variants,
    normalize_languages,
)
from app.schemas.benchmark import BenchmarkCreate


def test_language_codes_and_names_normalize_to_full_display_names():
    assert LANGUAGE_SUPPORT == ["English", "Chinese", "Arabic", "French", "Hindi", "Korean", "Multilingual"]
    assert canonical_language_name("en") == "English"
    assert canonical_language_name("Mandarin") == "Chinese"
    assert normalize_languages(["en", "English", "fr", "Multilingual"]) == ["English", "French", "Multilingual"]


def test_language_filter_variants_cover_canonical_and_legacy_values():
    assert language_storage_variants("English") == ("English", "en")
    assert language_storage_variants("multilingual") == ("Multilingual",)


def test_benchmark_schema_persists_full_language_names_from_legacy_input():
    benchmark = BenchmarkCreate(
        benchmark_name="Language test",
        benchmark_paper_title="Language test paper",
        language_support=["en", "French"],
    )

    assert [language.value for language in benchmark.language_support] == ["English", "French"]
