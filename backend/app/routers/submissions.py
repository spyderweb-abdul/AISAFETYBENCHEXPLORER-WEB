# Destination path: backend/app/routers/submissions.py
# Replaces the existing file in full. (Supersedes the earlier drafts
# from the previous session -- the only functional change is
# create_submission()'s dependency, swapped from get_current_user to
# require_researcher. See app/core/deps.py's require_researcher()
# docstring for the full rationale: an admin submitting through this
# endpoint was a real bug, not just a UI quirk -- it caused the same
# account to receive both admin-facing and submitter-facing
# notifications, and would let an admin review their own submission.
# get_submission()/list_my_submissions() still use get_current_user
# since admins legitimately need to look up any submission by id, and
# a researcher needs to see their own history -- only the WRITE path
# that creates a new community submission is now researcher-only.)

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.agent_runner import run_extraction
from app.core.audit import log_action
from app.core.config import settings
from app.core.deps import get_current_user, require_admin, require_researcher
from app.core.notifications import notify_admins, notify_user
from app.core.rate_limit import limiter
from app.core.submission_runner import (
    SubmissionBlockedError,
    _find_duplicate,
    _recent_consecutive_rejections,
    submit_community_extraction,
)
from app.db.session import get_db
from app.models.orm import Benchmark, ExtractionJob, Submission, User
from app.schemas.submission import SubmissionCreate, SubmissionOut, SubmissionReextract, SubmissionReview

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/day")
def create_submission(
    request: Request,
    payload: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Researcher-only (see require_researcher -- admins are
    structurally excluded, not just discouraged). Runs the extraction
    inline via BackgroundTasks, mirroring the existing admin Agent
    Extraction Panel's dispatch pattern in app/routers/extraction.py --
    see submission_runner.py for the full domain-check/quality-gate/
    notification workflow this triggers.
    """
    duplicate_reason = _find_duplicate(db, payload.source_value)
    if duplicate_reason:
        raise HTTPException(status_code=409, detail=duplicate_reason)

    rejection_streak = _recent_consecutive_rejections(db, current_user.id)
    if rejection_streak >= settings.MAX_CONSECUTIVE_REJECTIONS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Your last {rejection_streak} submissions were not approved. "
                "New submissions are paused for your account -- contact an admin."
            ),
        )

    placeholder = Submission(
        submitter_user_id=current_user.id,
        source_type="doi",
        source_value=payload.source_value,
        model_used=settings.COMMUNITY_SUBMISSION_MODEL,
        status="submitted",
    )
    db.add(placeholder)
    db.commit()
    db.refresh(placeholder)

    background_tasks.add_task(
        _run_submission_background,
        placeholder_id=placeholder.id,
        submitter_user_id=current_user.id,
        source_value=payload.source_value,
        db=db,
    )
    return placeholder


def _run_submission_background(placeholder_id: uuid.UUID, submitter_user_id: uuid.UUID, source_value: str, db: Session) -> None:
    placeholder = db.query(Submission).filter(Submission.id == placeholder_id).first()
    if placeholder is None:
        return
    try:
        db.delete(placeholder)
        db.commit()
        submit_community_extraction(
            db=db,
            submitter_user_id=submitter_user_id,
            source_type="doi",
            source_value=source_value,
            openai_api_key=settings.OPENAI_API_KEY,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            semantic_scholar_api_key=settings.SEMANTIC_SCHOLAR_API_KEY,
        )
    except SubmissionBlockedError as exc:
        notify_user(
            db, submitter_user_id, "submission_declined",
            title="Your submission could not be queued",
            body=str(exc), link_path="/submit",
        )
        db.commit()


@router.get("/mine", response_model=list[SubmissionOut])
def list_my_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Submission)
        .filter(Submission.submitter_user_id == current_user.id)
        .order_by(Submission.created_at.desc())
        .all()
    )


@router.get("", response_model=list[SubmissionOut])
def list_submissions(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(Submission)
    if status_filter:
        q = q.filter(Submission.status == status_filter)
    return q.order_by(Submission.created_at.desc()).all()


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "admin" and submission.submitter_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your submission")
    return submission


@router.post("/{submission_id}/review", response_model=SubmissionOut)
def review_submission(
    submission_id: uuid.UUID,
    payload: SubmissionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Submission status is '{submission.status}'; only pending_review submissions can be reviewed",
        )
    if payload.decision in ("reject", "needs_better_extraction") and not payload.reviewer_notes:
        raise HTTPException(
            status_code=400,
            detail="reviewer_notes is required when rejecting or requesting a better extraction",
        )
    if submission.submitter_user_id == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot review your own submission.",
        )

    benchmark = None
    if submission.result_benchmark_id:
        benchmark = db.query(Benchmark).filter(Benchmark.id == submission.result_benchmark_id).first()

    if payload.decision == "approve":
        submission.status = "approved"
        if benchmark:
            benchmark.status = "published"
        notify_body = "Your submission was approved and is now published."
        if payload.reviewer_notes:
            notify_body += f" Reviewer notes: {payload.reviewer_notes}"
        notify_type = "submission_approved"
    elif payload.decision == "reject":
        submission.status = "rejected"
        if benchmark:
            benchmark.status = "rejected"
        notify_body = f"Your submission was declined. Reason: {payload.reviewer_notes}"
        notify_type = "submission_declined"
    else:
        submission.status = "needs_better_extraction"
        notify_body = (
            f"Your submission needs a higher-quality extraction before it can "
            f"be published. Reviewer notes: {payload.reviewer_notes} An admin "
            "will re-run extraction with a more capable model; you'll be "
            "notified once it's ready for review again."
        )
        notify_type = "submission_needs_reextraction"

    submission.admin_reviewer_id = current_user.id
    submission.admin_review_notes = payload.reviewer_notes
    submission.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    notify_user(
        db, submission.submitter_user_id, notify_type,
        title="Update on your benchmark submission",
        body=notify_body,
        link_path="/submit",
    )
    db.commit()
    db.refresh(submission)
    return submission


def _run_reextraction_background(submission_id: uuid.UUID, job_id: uuid.UUID, superseded_benchmark_id: uuid.UUID | None, db: Session) -> None:
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if job is None or submission is None:
        return

    run_extraction(
        job_id=job.id,
        source_type=job.source_type,
        source_value=job.source_value,
        model_used=job.model_used,
        submitted_by=job.submitted_by,
        db=db,
        openai_api_key=settings.OPENAI_API_KEY,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        semantic_scholar_api_key=settings.SEMANTIC_SCHOLAR_API_KEY,
    )

    db.refresh(job)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()

    if superseded_benchmark_id:
        old_benchmark = db.query(Benchmark).filter(Benchmark.id == superseded_benchmark_id).first()
        if old_benchmark and old_benchmark.status != "rejected":
            old_benchmark.status = "rejected"
            log_action(
                db, table_name="benchmarks", record_id=old_benchmark.id, action="update",
                changed_by=None,
                diff={"reason": f"Superseded by re-extraction for submission {submission_id}"},
            )

    if job.status == "failed" or job.result_benchmark_id is None:
        submission.status = "failed"
        db.commit()
        notify_user(
            db, submission.submitter_user_id, "submission_failed_extraction",
            title="Re-extraction of your benchmark submission failed",
            body=f"The requested higher-quality re-extraction failed. Reason: {job.failure_reason or 'Unknown.'}",
            link_path="/submit",
        )
        db.commit()
        return

    new_benchmark = db.query(Benchmark).filter(Benchmark.id == job.result_benchmark_id).first()
    new_benchmark.submission_source = "community"
    new_benchmark.submitted_by_user_id = submission.submitter_user_id

    submission.result_benchmark_id = new_benchmark.id
    submission.quality_score = job.quality_score
    submission.status = "pending_review"
    db.commit()

    notify_admins(
        db, "submission_queued_for_review",
        title=f"Re-extraction ready for review: {new_benchmark.benchmark_name}",
        body=f"Re-extracted with {job.model_used} at the reviewing admin's request. Quality score: {job.quality_score}.",
        link_path=f"/admin/submissions/{submission.id}",
    )
    db.commit()


@router.post("/{submission_id}/reextract", response_model=SubmissionOut, status_code=status.HTTP_202_ACCEPTED)
def reextract_submission(
    submission_id: uuid.UUID,
    payload: SubmissionReextract,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != "needs_better_extraction":
        raise HTTPException(
            status_code=400,
            detail=f"Submission status is '{submission.status}'; only needs_better_extraction submissions can be re-extracted",
        )

    superseded_benchmark_id = submission.result_benchmark_id

    job = ExtractionJob(
        source_type=submission.source_type,
        source_value=submission.source_value,
        model_used=payload.model_used,
        status="queued",
        submitted_by=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    submission.extraction_job_id = job.id
    submission.model_used = payload.model_used
    submission.status = "extracting"
    db.commit()

    background_tasks.add_task(
        _run_reextraction_background,
        submission_id=submission.id,
        job_id=job.id,
        superseded_benchmark_id=superseded_benchmark_id,
        db=db,
    )
    db.refresh(submission)
    return submission
