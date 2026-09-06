"""Canonical language labels used across extraction and catalogue metadata."""

from __future__ import annotations

from typing import Iterable


LANGUAGE_CODE_TO_NAME = {
    "en": "English",
    "zh": "Chinese",
    "ar": "Arabic",
    "fr": "French",
    "hi": "Hindi",
    "ko": "Korean",
}
LANGUAGE_SUPPORT = [*LANGUAGE_CODE_TO_NAME.values(), "Multilingual"]

_ALIASES = {
    **LANGUAGE_CODE_TO_NAME,
    **{name.casefold(): name for name in LANGUAGE_CODE_TO_NAME.values()},
    "mandarin": "Chinese",
    "mandarin chinese": "Chinese",
    "simplified chinese": "Chinese",
    "traditional chinese": "Chinese",
    "multi": "Multilingual",
    "multiple": "Multilingual",
    "multilingual": "Multilingual",
}


def canonical_language_name(value: object) -> str | None:
    """Return a full controlled-language label for a code, label, or alias."""
    normalized = " ".join(str(value or "").strip().split()).casefold()
    return _ALIASES.get(normalized)


def normalize_languages(values: Iterable[object] | object | None) -> list[str]:
    """Normalize and de-duplicate language metadata while preserving order."""
    if values is None:
        return []
    candidates = [values] if isinstance(values, str) else values
    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        name = canonical_language_name(value)
        if name and name not in seen:
            seen.add(name)
            normalized.append(name)
    return normalized


def language_storage_variants(value: object) -> tuple[str, ...]:
    """Match canonical values and legacy ISO codes during the data transition."""
    name = canonical_language_name(value)
    if not name:
        cleaned = " ".join(str(value or "").strip().split())
        return (cleaned,) if cleaned else ()
    legacy_code = next((code for code, label in LANGUAGE_CODE_TO_NAME.items() if label == name), None)
    return (name, legacy_code) if legacy_code else (name,)
