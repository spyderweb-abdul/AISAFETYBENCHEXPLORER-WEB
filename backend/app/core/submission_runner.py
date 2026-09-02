from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.agent_runner import run_extraction
from app.core.config import settings
from app.core.domain_relevance import check_domain_relevance
from app.core.notifications import notify_admins, notify_user
from app.models.orm import Benchmark, ExtractionJob, Submission

logger = logging.getLogger(__name__)


class SubmissionBlockedError(Exception):
    """Raised when a submission cannot even be queued (duplicate or
    the submitter is currently rate-limited by consecutive rejections).
    The router catches this and returns a 400 with the message as-is."""


def _recent_consecutive_rejections(db: Session, user_id: uuid.UUID) -> int:
    recent = (
        db.query(Submission)
        .filter(Submission.submitter_user_id == user_id)
        .order_by(Submission.created_at.desc())
        .limit(settings.MAX_CONSECUTIVE_REJECTIONS)
        .all()
    )
    count = 0
    for sub in recent:
        if sub.status in ("rejected", "failed"):
            count += 1
        else:
            break
    return count


def _find_duplicate(db: Session, source_value: str) -> str | None:
    """Returns a human-readable reason string if this source_value
    looks like a duplicate of an in-flight or already-catalogued
    submission, else None."""
    existing_submission = (
        db.query(Submission)
        .filter(
            Submission.source_value == source_value,
            Submission.status.notin_(["rejected", "failed"]),
        )
        .first()
    )
    if existing_submission:
        return (
            f"A submission for this source is already in progress or under "
            f"review (submission {existing_submission.id}, status="
            f"{existing_submission.status})."
        )

    existing_benchmark = (
        db.query(Benchmark)
        .filter(
            Benchmark.paper_link == source_value,
            Benchmark.status.in_(["published", "pending_review"]),
        )
        .first()
    )
    if existing_benchmark:
        return (
            f"This paper is already catalogued as '{existing_benchmark.benchmark_name}' "
            f"(status={existing_benchmark.status})."
        )
    return None


def submit_community_extraction(
    db: Session,
    submitter_user_id: uuid.UUID,
    source_type: str,
    source_value: str,
    openai_api_key: str = "",
    anthropic_api_key: str = "",
    semantic_scholar_api_key: str = "",
) -> Submission:
    """Runs the full gated community submission workflow synchronously
    (intended to be called from a FastAPI BackgroundTask, mirroring how
    app/routers/extraction.py's submit_job() calls run_extraction()
    directly rather than via Celery). Returns the final Submission row.

    Raises SubmissionBlockedError before spending any model call if the
    submission is a duplicate or the submitter is currently blocked by
    the consecutive-rejection guard.
    """
    duplicate_reason = _find_duplicate(db, source_value)
    if duplicate_reason:
        raise SubmissionBlockedError(duplicate_reason)

    rejection_streak = _recent_consecutive_rejections(db, submitter_user_id)
    if rejection_streak >= settings.MAX_CONSECUTIVE_REJECTIONS:
        raise SubmissionBlockedError(
            f"Your last {rejection_streak} submissions were not approved. "
            "New submissions are paused for your account until one of your "
            "existing submissions is approved, or an admin reviews your "
            "account. This is an automated abuse-prevention measure, not a "
            "permanent block -- contact an admin if you believe this is in "
            "error."
        )

    model_used = settings.COMMUNITY_SUBMISSION_MODEL

    submission = Submission(
        submitter_user_id=submitter_user_id,
        source_type=source_type,
        source_value=source_value,
        model_used=model_used,
        status="submitted",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    job = ExtractionJob(
        source_type=source_type,
        source_value=source_value,
        model_used=model_used,
        status="queued",
        submitted_by=submitter_user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    submission.extraction_job_id = job.id
    submission.status = "extracting"
    db.commit()

    run_extraction(
        job_id=job.id,
        source_type=source_type,
        source_value=source_value,
        model_used=model_used,
        submitted_by=submitter_user_id,
        db=db,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        semantic_scholar_api_key=semantic_scholar_api_key,
    )

    db.refresh(job)
    submission = db.query(Submission).filter(Submission.id == submission.id).first()

    if job.status == "failed" or job.result_benchmark_id is None:
        submission.status = "failed"
        db.commit()
        notify_user(
            db,
            submitter_user_id,
            "submission_failed_extraction",
            title="Your benchmark submission could not be extracted",
            body=(
                f"We could not extract benchmark metadata from {source_value}. "
                f"Reason: {job.failure_reason or 'Unknown extraction failure.'} "
                "You can try resubmitting, or contact an admin if this persists."
            ),
            link_path=f"/submit?highlight={submission.id}",
        )
        db.commit()
        return submission

    benchmark = db.query(Benchmark).filter(Benchmark.id == job.result_benchmark_id).first()
    submission.result_benchmark_id = benchmark.id
    submission.quality_score = job.quality_score

    benchmark.submission_source = "community"
    benchmark.submitted_by_user_id = submitter_user_id

    domain_passed, domain_reason = check_domain_relevance(
        benchmark.task_type, benchmark.benchmark_name, benchmark.description or ""
    )
    submission.domain_check_passed = domain_passed
    submission.domain_check_reason = domain_reason

    quality_score = float(job.quality_score) if job.quality_score is not None else 0.0
    auto_reject = (domain_passed is False) and (quality_score < settings.MIN_QUALITY_SCORE_FOR_REVIEW)

    if auto_reject:
        submission.status = "rejected"
        benchmark.status = "rejected"
        db.commit()
        notify_user(
            db,
            submitter_user_id,
            "submission_declined",
            title="Your benchmark submission was not accepted",
            body=(
                f"Submission for {source_value} was automatically declined. "
                f"Domain check: {domain_reason} Quality score: {quality_score:.2f} "
                f"(minimum required: {settings.MIN_QUALITY_SCORE_FOR_REVIEW}). "
                "If you believe this paper is genuinely AI-safety-related, "
                "please contact an admin with more context, or try resubmitting "
                "with a more precise DOI/arXiv ID."
            ),
            link_path=f"/submit?highlight={submission.id}",
        )
    else:
        submission.status = "pending_review"
        db.commit()
        notify_admins(
            db,
            "submission_queued_for_review",
            title=f"New community submission awaiting review: {benchmark.benchmark_name}",
            body=(
                f"Submitted via {model_used}. Quality score: {quality_score:.2f}. "
                f"Domain check: {'passed' if domain_passed else 'borderline' if domain_passed is None else 'failed'} "
                f"-- {domain_reason}"
            ),
            link_path=f"/admin/submissions?highlight={submission.id}",
        )

    db.commit()
    db.refresh(submission)
    return submission