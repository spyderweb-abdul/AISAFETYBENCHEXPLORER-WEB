"""Persistence helpers for verified paper metadata and citation history."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.core.paper_fetcher import resolve_paper_metadata
from app.models.orm import Benchmark, CitationSnapshot, PaperMetadata


def _parse_publication_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 4 and text.isdigit():
            return date(int(text), 1, 1)
        if len(text) == 7:
            return datetime.strptime(text, "%Y-%m").date()
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def persist_paper_metadata(
    db: Session, benchmark: Benchmark, resolved: dict[str, Any]
) -> tuple[PaperMetadata, int | None]:
    """Upsert current paper metadata and append a snapshot on a valid count."""
    metadata = benchmark.paper_metadata
    if metadata is None:
        metadata = PaperMetadata(id=uuid.uuid4(), benchmark_id=benchmark.id)
        db.add(metadata)

    for field in (
        "doi", "arxiv_id", "semantic_scholar_paper_id", "canonical_title",
        "authors", "venue", "is_open_access", "open_access_url",
        "metadata_source",
    ):
        value = resolved.get(field)
        if value not in (None, ""):
            setattr(metadata, field, value)

    publication_date = _parse_publication_date(resolved.get("publication_date"))
    if publication_date is not None:
        metadata.publication_date = publication_date

    now = datetime.now(timezone.utc)
    metadata.last_refreshed_at = now
    metadata.last_error = resolved.get("error")

    count = resolved.get("citation_count")
    if isinstance(count, bool):
        count = None
    elif count is not None:
        try:
            count = max(0, int(count))
        except (TypeError, ValueError):
            count = None
    if count is not None:
        metadata.citation_count = count
        metadata.citation_source = resolved.get("citation_source") or "Unknown"
        metadata.citation_checked_at = now
        db.add(CitationSnapshot(
            id=uuid.uuid4(),
            benchmark_id=benchmark.id,
            citation_count=count,
            source=metadata.citation_source,
            fetched_at=now,
        ))
    return metadata, count


def refresh_paper_metadata_for_benchmark(
    db: Session,
    benchmark: Benchmark,
    *,
    source_type: str | None = None,
    source_value: str | None = None,
    fetched: dict[str, Any] | None = None,
    semantic_scholar_api_key: str = "",
) -> tuple[PaperMetadata, int | None]:
    """Resolve and persist metadata without committing the caller's session."""
    if source_value is None:
        source_value = benchmark.paper_link or benchmark.benchmark_paper_title
    resolved = resolve_paper_metadata(
        source_type,
        source_value,
        fetched=fetched,
        semantic_scholar_api_key=semantic_scholar_api_key,
    )
    return persist_paper_metadata(db, benchmark, resolved)
