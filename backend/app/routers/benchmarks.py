from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user, require_admin
from app.core.rate_limit import limiter
from app.core.safety_dimension_classifier import classify_safety_dimensions
from app.core.use_case_classifier import classify_use_cases
from app.db.session import get_db
from app.models.orm import Benchmark, ExtractionJob
from app.schemas.benchmark import BenchmarkCreate, BenchmarkOut, BenchmarkUpdate
from app.schemas.extraction_job import ExtractionJobReview

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


def _stamp_classifications(obj: Benchmark) -> None:
    """Phase 5: recomputes use_cases and safety_dimensions from the
    object's current task_type/description/benchmark_name, always
    overwriting whatever was there before. Called on every create and
    update so these two fields can never drift out of sync with the
    fields they're derived from -- there is no user-settable path for
    them (BenchmarkCreate/BenchmarkUpdate do not declare these fields
    at all, and BenchmarkUpdate has extra="forbid")."""
    obj.use_cases = classify_use_cases(obj.task_type, obj.description, obj.benchmark_name)
    obj.safety_dimensions = classify_safety_dimensions(obj.task_type)


@router.get("", response_model=list[BenchmarkOut])
@limiter.limit("60/minute")
def list_benchmarks(
    request: Request,
    task_type: Optional[str] = Query(None),
    use_case: Optional[str] = Query(
        None,
        description="Filter by a Phase 5 use-case category (see app/core/use_case_classifier.py's USE_CASE_CATEGORIES).",
    ),
    complexity_level: Optional[str] = Query(None),
    license: Optional[str] = Query(
        None,
        description=(
            "Filter by license, case-insensitive partial match (e.g. "
            "'MIT' matches 'MIT License'). Closes the Phase 5 gap where "
            "License was a client-side-only filter on /browse."
        ),
    ),
    language_support: Optional[str] = Query(
        None,
        description=(
            "Filter by a supported language from app/core/"
            "controlled_vocab.py's LANGUAGE_SUPPORT list (exact match "
            "against the language_support array column). Closes the "
            "Phase 5 gap where Language Support was a client-side-only "
            "filter on /browse."
        ),
    ),
    release_date_from: Optional[date] = Query(
        None,
        description="Only include benchmarks with release_date on or after this date (YYYY-MM-DD).",
    ),
    release_date_to: Optional[date] = Query(
        None,
        description="Only include benchmarks with release_date on or before this date (YYYY-MM-DD).",
    ),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(
        None,
        description=(
            "Filter by benchmark status (published, pending_review, "
            "rejected). If omitted, defaults to excluding 'rejected' "
            "benchmarks only, so discarded extraction attempts never show "
            "up by default -- pending_review benchmarks still show by "
            "default since admins currently rely on seeing them in this "
            "list. Pass status=published explicitly for a curated, "
            "public-facing view (e.g. the Phase 5 researcher dashboard), "
            "or status=rejected / status=pending_review to review a "
            "specific bucket."
        ),
    ),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Benchmark)
    if status:
        q = q.filter(Benchmark.status == status)
    else:
        q = q.filter(Benchmark.status != "rejected")
    if task_type:
        q = q.filter(Benchmark.task_type.any(task_type))
    if use_case:
        q = q.filter(Benchmark.use_cases.any(use_case))
    if complexity_level:
        q = q.filter(Benchmark.complexity_level == complexity_level)
    if license:
        q = q.filter(Benchmark.license.ilike(f"%{license}%"))
    if language_support:
        q = q.filter(Benchmark.language_support.any(language_support))
    if release_date_from:
        q = q.filter(Benchmark.release_date >= release_date_from)
    if release_date_to:
        q = q.filter(Benchmark.release_date <= release_date_to)
    if search:
        q = q.filter(Benchmark.benchmark_name.ilike(f"%{search}%"))
    return q.order_by(Benchmark.benchmark_name).offset(offset).limit(limit).all()


@router.get("/{benchmark_id}", response_model=BenchmarkOut)
@limiter.limit("60/minute")
def get_benchmark(request: Request, benchmark_id: UUID, db: Session = Depends(get_db)):
    obj = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return obj


@router.post("", response_model=BenchmarkOut, status_code=201)
def create_benchmark(
    payload: BenchmarkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = Benchmark(**payload.model_dump(), created_by_user_id=current_user.id)
    _stamp_classifications(obj)
    db.add(obj)
    db.flush()

    log_action(
        db, table_name="benchmarks", record_id=obj.id, action="create",
        changed_by=current_user.id, diff=payload.model_dump(),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{benchmark_id}", response_model=BenchmarkOut)
def update_benchmark(
    benchmark_id: UUID,
    payload: BenchmarkUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(obj, field) for field in changes}

    for field, value in changes.items():
        setattr(obj, field, value)
    obj.updated_by_user_id = current_user.id
    _stamp_classifications(obj)

    log_action(
        db, table_name="benchmarks", record_id=obj.id, action="update",
        changed_by=current_user.id, diff={"before": before, "after": changes},
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{benchmark_id}/review", response_model=BenchmarkOut)
def review_benchmark(
    benchmark_id: UUID,
    payload: ExtractionJobReview,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """FIX (2026-08-23): benchmark-centric review action, reachable
    directly from the benchmark edit page. Closes a real dead end: a
    benchmark can sit at status="pending_review" while its
    ExtractionJob is already status="done" (a high quality_score run
    skips "needs_review" entirely), which made it invisible to the
    Extraction Panel's Pending Review queue (previously filtered on
    job.status=="needs_review" only) and there was no admin-frontend
    control to change Benchmark.status at all otherwise --
    BenchmarkForm.tsx never exposed status as an editable field.

    This endpoint sets Benchmark.status directly and, if a linked
    ExtractionJob exists (result_benchmark_id == benchmark_id), updates
    its status too for consistency with POST /extraction/jobs/{id}/review
    -- but does not require one to exist, since the review action
    belongs to the benchmark, not the job."""
    obj = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    if obj.status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Benchmark status is '{obj.status}'; only pending_review benchmarks can be reviewed here",
        )

    before_status = obj.status
    obj.status = "published" if payload.approve else "rejected"
    obj.updated_by_user_id = current_user.id

    linked_job = (
        db.query(ExtractionJob)
        .filter(ExtractionJob.result_benchmark_id == benchmark_id)
        .order_by(ExtractionJob.created_at.desc())
        .first()
    )
    if linked_job is not None:
        linked_job.status = "done" if payload.approve else "failed"

    log_action(
        db, table_name="benchmarks", record_id=obj.id,
        action="approve" if payload.approve else "reject",
        changed_by=current_user.id,
        diff={"before": before_status, "after": obj.status, "reviewer_note": payload.reviewer_note},
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{benchmark_id}", status_code=204)
def delete_benchmark(
    benchmark_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    log_action(
        db, table_name="benchmarks", record_id=obj.id, action="delete",
        changed_by=current_user.id, diff={"benchmark_name": obj.benchmark_name},
    )
    db.delete(obj)
    db.commit()
