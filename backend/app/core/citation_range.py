from app.core.complexity_classifier import get_popular_citation_threshold

_LOW_CEILING = 50
_MEDIUM_CEILING = 100


def compute_citation_range(cited_by: int | None) -> str:
    """Returns a human-readable citation bucket label, e.g. "0-50",
    "51-100", "101-500", "501+" (with the top bucket's boundary
    following the live Popular threshold instead of a hardcoded 500).
    None/negative cited_by is treated as 0."""
    count = cited_by if isinstance(cited_by, int) and cited_by > 0 else 0
    popular_threshold = get_popular_citation_threshold()

    if count > popular_threshold:
        return f"{popular_threshold + 1}+"
    if count > _MEDIUM_CEILING:
        return f"{_MEDIUM_CEILING + 1}-{popular_threshold}"
    if count > _LOW_CEILING:
        return f"{_LOW_CEILING + 1}-{_MEDIUM_CEILING}"
    return f"0-{_LOW_CEILING}"
