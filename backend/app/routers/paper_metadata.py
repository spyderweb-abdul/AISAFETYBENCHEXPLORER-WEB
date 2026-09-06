"""Read-only endpoints for verified bibliographic metadata."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.rate_limit import limiter
from app.models.orm import Benchmark, CitationSnapshot, PaperMetadata
from app.schemas.paper_metadata import CitationSnapshotOut, PaperMetadataOut


router = APIRouter(prefix="/paper-metadata", tags=["paper-metadata"])


@router.get("/benchmarks/{benchmark_id}", response_model=PaperMetadataOut | None)
@limiter.limit("60/minute")
def get_paper_metadata(request: Request, benchmark_id: UUID, db: Session = Depends(get_db)):
    if not db.query(Benchmark.id).filter(Benchmark.id == benchmark_id).first():
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return db.query(PaperMetadata).filter(PaperMetadata.benchmark_id == benchmark_id).first()


@router.get("/benchmarks/{benchmark_id}/citation-history", response_model=list[CitationSnapshotOut])
@limiter.limit("60/minute")
def get_citation_history(
    request: Request,
    benchmark_id: UUID,
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if not db.query(Benchmark.id).filter(Benchmark.id == benchmark_id).first():
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return (
        db.query(CitationSnapshot)
        .filter(CitationSnapshot.benchmark_id == benchmark_id)
        .order_by(CitationSnapshot.fetched_at.desc())
        .limit(limit)
        .all()
    )
