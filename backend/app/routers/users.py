# Destination path: backend/app/routers/users.py
# New file.
#
# Phase 6 item 4 support: minimal admin-only user management, needed
# for the is_trusted_submitter toggle referenced throughout the
# submission workflow (see submission_runner.py / domain_relevance.py
# docstrings). Deliberately minimal -- this is not a general user-CRUD
# router, just what the submission-review workflow needs: a way for an
# admin to see submitters and toggle their trust flag.

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.orm import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    search: str | None = Query(None, description="Filter by partial email match"),
    role: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(User)
    if search:
        q = q.filter(User.email.ilike(f"%{search}%"))
    if role:
        q = q.filter(User.role == role)
    return q.order_by(User.created_at.desc()).limit(200).all()


@router.post("/{user_id}/trust", response_model=UserOut)
def set_trusted_submitter(
    user_id: uuid.UUID,
    trusted: bool = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Toggles a user's is_trusted_submitter flag. Trusted submitters'
    borderline/failed domain checks are queued for manual review
    instead of being auto-rejected -- see domain_relevance.py and
    submission_runner.py. Does NOT bypass the consecutive-rejection
    submission block, which applies to everyone."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_trusted_submitter = trusted
    db.commit()
    db.refresh(user)
    return user
