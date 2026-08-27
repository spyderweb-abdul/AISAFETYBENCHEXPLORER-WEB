# Destination path: backend/app/scripts/cleanup_mismatched_notifications.py
# New file.
#
# One-time cleanup for Notification rows created before the
# require_researcher fix (see routers/submissions.py and deps.py),
# back when an admin account could submit through the community
# workflow and therefore accumulate notifications intended for a
# researcher (submission_approved/declined/needs_reextraction/
# failed_extraction) on what is now an admin-only account.
#
# This is almost certainly the actual explanation for "as an admin, I
# am still seeing researcher's tailored notifications": those rows are
# real, historical data from before the role separation existed, not a
# live bug in the current code (see the audience-mismatch warning now
# logged by notify_user() in app/core/notifications.py for a
# forward-looking safeguard against this recurring).
#
# Usage (run inside the backend container or with the backend's venv
# activated, DATABASE_URL pointing at the right database):
#   python -m app.scripts.cleanup_mismatched_notifications --dry-run
#   python -m app.scripts.cleanup_mismatched_notifications
#
# --dry-run prints what WOULD be deleted without deleting anything.
# Without --dry-run, matching rows are deleted permanently -- there is
# no undo, since these are notifications, not benchmark data.

from __future__ import annotations

import argparse

from app.core.notifications import NOTIFICATION_TYPE_AUDIENCE
from app.db.session import SessionLocal
from app.models.orm import Notification, User


def main(dry_run: bool) -> None:
    db = SessionLocal()
    try:
        removed = 0
        for notification_type, expected_role in NOTIFICATION_TYPE_AUDIENCE.items():
            mismatched = (
                db.query(Notification)
                .join(User, Notification.user_id == User.id)
                .filter(Notification.notification_type == notification_type, User.role != expected_role)
                .all()
            )
            for entry in mismatched:
                recipient = db.query(User).filter(User.id == entry.user_id).first()
                print(
                    f"{'[DRY RUN] Would remove' if dry_run else 'Removing'}: "
                    f"notification {entry.id} (type={notification_type}, "
                    f"intended for role={expected_role}) currently on account "
                    f"{recipient.email if recipient else entry.user_id} "
                    f"(role={recipient.role if recipient else 'unknown'})"
                )
                if not dry_run:
                    db.delete(entry)
                removed += 1

        if not dry_run:
            db.commit()

        print(f"\n{'Would remove' if dry_run else 'Removed'} {removed} mismatched notification(s).")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted without deleting anything.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
