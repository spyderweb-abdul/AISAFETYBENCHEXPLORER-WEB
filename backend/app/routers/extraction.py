from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core.agent_runner import run_extraction
from app.db.session import get_db
from app.models.orm import Benchmark, ExtractionJob, User
from app.schemas.extraction_job import ExtractionJobCreate, ExtractionJobOut, ExtractionJobReview

router = APIRouter(prefix="/extraction", tags=["extraction"])


@router.post("/jobs", response_model=ExtractionJobOut, status_code=status.HTTP_202_ACCEPTED)
def submit_job(
    payload: ExtractionJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ExtractionJob:
    job = ExtractionJob(
        source_type=payload.source_type,
        source_value=payload.source_value,
        model_used=payload.model_used,
        status="queued",
        submitted_by=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        run_extraction,
        job_id=job.id,
        source_type=payload.source_type,
        source_value=payload.source_value,
        model_used=payload.model_used,
        submitted_by=current_user.id,
        db=db,
        openai_api_key=settings.OPENAI_API_KEY,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
    )
    return job


@router.get("/jobs", response_model=List[ExtractionJobOut])
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[ExtractionJob]:
    q = db.query(ExtractionJob)
    if status_filter:
        q = q.filter(ExtractionJob.status == status_filter)
    return q.order_by(ExtractionJob.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/jobs/{job_id}", response_model=ExtractionJobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ExtractionJob:
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/review", response_model=ExtractionJobOut)
def review_job(
    job_id: uuid.UUID,
    payload: ExtractionJobReview,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ExtractionJob:
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("needs_review", "done"):
        raise HTTPException(
            status_code=400,
            detail=f"Job status is '{job.status}'; only needs_review or done jobs can be reviewed",
        )
    if job.result_benchmark_id is None:
        raise HTTPException(status_code=400, detail="No result benchmark attached to this job")

    benchmark = db.query(Benchmark).filter(Benchmark.id == job.result_benchmark_id).first()
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Result benchmark not found")

    if payload.approve:
        benchmark.status = "published"
        job.status = "done"
    else:
        benchmark.status = "rejected"
        job.status = "failed"

    db.commit()
    db.refresh(job)
    return job
