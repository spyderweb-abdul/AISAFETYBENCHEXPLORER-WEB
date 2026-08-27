# Destination path: backend/app/core/notifications.py
# Replaces the existing file in full.
#
# CHANGE (role-clarity fix, this session): adds NOTIFICATION_TYPE_AUDIENCE,
# a fixed mapping of which role each notification_type is meant for.
# notify_user() now looks up the recipient's CURRENT role and logs a
# loud warning if it doesn't match the notification's intended
# audience -- this is a defense-in-depth observability signal, not a
# hard block (a role can legitimately change over time, e.g. a
# researcher account gets promoted to admin directly in the database,
# and that account's notification HISTORY from before the promotion
# is real and should not be silently deleted or hidden). Going
# forward, POST /submissions is already restricted to
# require_researcher (see deps.py / routers/submissions.py), so no
# NEW mismatched notification can be created by that path -- this
# warning exists to catch any future code path that might reintroduce
# the same class of bug, immediately and loudly in logs, rather than
# silently confusing whoever is using the account later.
#
# See also: backend/app/scripts/cleanup_mismatched_notifications.py,
# a one-time cleanup tool for pre-existing mismatched rows created
# before the require_researcher fix (e.g. from testing before the
# role split existed).

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.orm import Notification, User

logger = logging.getLogger(__name__)

# Fixed audience per notification_type. Used only for the
# defense-in-depth warning below and by the cleanup script -- not
# enforced as a hard block at write time.
NOTIFICATION_TYPE_AUDIENCE: dict[str, str] = {
    "submission_queued_for_review": "admin",
    "submission_approved": "researcher",
    "submission_declined": "researcher",
    "submission_needs_reextraction": "researcher",
    "submission_failed_extraction": "researcher",
}


def _send_email_best_effort(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST or not to_email:
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as exc:
        logger.warning("Best-effort notification email to %s failed: %s", to_email, exc)


def notify_user(
    db: Session,
    user_id: UUID,
    notification_type: str,
    title: str,
    body: str | None = None,
    link_path: str | None = None,
    send_email: bool = True,
) -> Notification:
    """Writes a Notification row for a single user and, if
    send_email=True and SMTP is configured, best-effort emails them
    too. Does not commit -- the caller controls the transaction
    boundary so this can be batched with the rest of a review/
    submission action's writes."""
    user = db.query(User).filter(User.id == user_id).first()

    expected_audience = NOTIFICATION_TYPE_AUDIENCE.get(notification_type)
    if user and expected_audience and user.role != expected_audience:
        logger.warning(
            "Notification audience mismatch: notification_type=%s is intended "
            "for role=%s, but recipient %s currently has role=%s. Writing it "
            "anyway (role history is preserved), but this may indicate a code "
            "path that should be using require_researcher/require_admin "
            "instead, or that this account's role changed after earlier "
            "activity under a different role.",
            notification_type, expected_audience, user_id, user.role,
        )

    entry = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        link_path=link_path,
    )
    db.add(entry)

    if send_email and user:
        full_body = body or ""
        if link_path:
            full_body += f"\n\nView: {settings.FRONTEND_BASE_URL}{link_path}"
        _send_email_best_effort(user.email, title, full_body)

    return entry


def notify_admins(
    db: Session,
    notification_type: str,
    title: str,
    body: str | None = None,
    link_path: str | None = None,
) -> list[Notification]:
    """Notifies every user with role="admin". Used when a community
    submission is queued for review, so admins don't have to
    proactively poll the review queue to notice new work."""
    admins = db.query(User).filter(User.role == "admin").all()
    entries = [
        notify_user(db, admin.id, notification_type, title, body, link_path)
        for admin in admins
    ]

    for extra_email in filter(None, (e.strip() for e in settings.ADMIN_NOTIFICATION_EMAILS_EXTRA.split(","))):
        full_body = body or ""
        if link_path:
            full_body += f"\n\nView: {settings.FRONTEND_BASE_URL}{link_path}"
        _send_email_best_effort(extra_email, title, full_body)

    return entries
