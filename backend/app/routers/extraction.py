# Destination path: backend/app/routers/extraction.py
# Replaces the existing file in full.
#
# CHANGE (2026-08-28): new POST /extraction/jobs/{job_id}/rerun endpoint.
# Lets an admin re-run the admin extraction pipeline on a job that has
# already produced a benchmark, UPDATING that same benchmark row in
# place (via agent_runner.run_extraction()'s new reuse_benchmark_id
# parameter -- see agent_runner_reuse_benchmark_patch.py) instead of
# creating a second, duplicate catalogue entry for the same paper.
# This is the direct fix for: "I processed the same paper through the
# admin's extraction, hoping the already catalogued benchmark will be
# updated, however, a new entry of the same benchmark was catalogued
# instead."

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cost_tracking import compute_run_variance
from app.core.deps import get_current_user, require_admin
from app.core.agent_runner import run_extraction
from app.db.session import get_db
from app.models.orm import Benchmark, ExtractionJob, User
from app.schemas.extraction_job import (
    ExtractionJobCreate,
    ExtractionJobOut,
    ExtractionJobReview,
    JobVarianceOut,
)

router = APIRouter(prefix="/extraction", tags=["extraction"])


def _attach_benchmark_statuses(db: Session, jobs: list[ExtractionJob]) -> list[ExtractionJob]:
    """FIX (2026-08-23): populates each job's result_benchmark_status
    (not a real column -- see ExtractionJobOut) via one batched lookup,
    so the frontend Pending Review queue can filter on the benchmark's
    actual status instead of the job's status, which previously hid
    every pending_review benchmark whose extraction job had a high
    enough quality_score to be marked job.status="done"."""
    benchmark_ids = [job.result_benchmark_id for job in jobs if job.result_benchmark_id]
    status_by_id: dict[uuid.UUID, str] = {}
    if benchmark_ids:
        rows = (
            db.query(Benchmark.id, Benchmark.status)
            .filter(Benchmark.id.in_(benchmark_ids))
            .all()
        )
        status_by_id = {row.id: row.status for row in rows}

    for job in jobs:
        job.result_benchmark_status = status_by_id.get(job.result_benchmark_id)
    return jobs


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
        semantic_scholar_api_key=settings.SEMANTIC_SCHOLAR_API_KEY,
    )
    job.result_benchmark_status = None
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
    jobs = q.order_by(ExtractionJob.created_at.desc()).offset(skip).limit(limit).all()
    return _attach_benchmark_statuses(db, jobs)


@router.get("/jobs/variance", response_model=JobVarianceOut)
def get_job_variance(
    source_value: str = Query(
        ..., description="The exact source_value (DOI, arXiv ID, or PDF URL) to group runs by"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> JobVarianceOut:
    """Roadmap item 12: run-to-run variance and total cost across every
    ExtractionJob that shares this source_value. Registered before
    GET /jobs/{job_id} so "variance" is never mistaken for a job UUID.
    """
    jobs = (
        db.query(ExtractionJob)
        .filter(ExtractionJob.source_value == source_value)
        .order_by(ExtractionJob.created_at)
        .all()
    )
    stats = compute_run_variance([job.quality_score for job in jobs])
    total_cost = None
    if jobs:
        priced_jobs = [job.estimated_cost_usd for job in jobs if job.estimated_cost_usd is not None]
        if priced_jobs:
            total_cost = sum(priced_jobs, Decimal("0"))

    return JobVarianceOut(
        source_value=source_value,
        run_count=stats["run_count"],
        mean_quality_score=stats["mean_quality_score"],
        stddev_quality_score=stats["stddev_quality_score"],
        total_estimated_cost_usd=total_cost,
        job_ids=[job.id for job in jobs],
    )


@router.get("/jobs/{job_id}", response_model=ExtractionJobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ExtractionJob:
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _attach_benchmark_statuses(db, [job])[0]


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
    job.result_benchmark_status = benchmark.status
    return job


@router.post("/jobs/{job_id}/rerun", response_model=ExtractionJobOut, status_code=status.HTTP_202_ACCEPTED)
def rerun_job(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ExtractionJob:
    """NEW (2026-08-28): re-runs the admin extraction pipeline for a job
    that already has a result_benchmark_id, UPDATING that same
    Benchmark row in place instead of creating a duplicate. This is
    the admin-panel equivalent of the submissions.py reextract flow,
    for jobs submitted directly through the Agent Extraction Panel
    rather than through the community submission form.

    Requires job.result_benchmark_id to already be set -- if this job
    never produced a benchmark (e.g. it failed before extraction
    completed), use POST /extraction/jobs with the same source_value
    instead, since there is nothing yet to update in place.
    """
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.result_benchmark_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "This job has no result_benchmark_id to update -- it never "
                "produced a benchmark. Submit a new job via POST "
                "/extraction/jobs instead."
            ),
        )

    reuse_benchmark_id = job.result_benchmark_id

    job.status = "queued"
    job.failure_reason = None
    job.completed_at = None
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        run_extraction,
        job_id=job.id,
        source_type=job.source_type,
        source_value=job.source_value,
        model_used=job.model_used,
        submitted_by=job.submitted_by or current_user.id,
        db=db,
        openai_api_key=settings.OPENAI_API_KEY,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        semantic_scholar_api_key=settings.SEMANTIC_SCHOLAR_API_KEY,
        reuse_benchmark_id=reuse_benchmark_id,
    )
    job.result_benchmark_status = None
    return job

