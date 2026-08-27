# Destination path: backend/app/core/deps.py
# Replaces the existing file in full.
#
# CHANGE (role-conflict fix, this session): adds require_researcher(),
# mirroring require_admin()'s pattern. Used by
# POST /submissions (routers/submissions.py) to structurally prevent
# admin accounts from submitting through the community workflow --
# closes a real bug where an admin testing /submit would receive both
# admin-facing ("new submission to review") and submitter-facing
# ("your submission was declined") notifications on the same account,
# and would be able to review their own submission (a self-review
# integrity problem, not just a UI confusion issue).

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.orm import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_email = payload.get("sub")
        if user_email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == user_email).first()
    if user is None:
        raise credentials_exception
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def require_researcher(user: User = Depends(get_current_user)) -> User:
    """Restricts an endpoint to researcher accounts only. Admins are
    deliberately EXCLUDED here, not just un-required -- see the module
    docstring above for why an admin submitting through the community
    workflow is a structural problem (mixed notifications, self-review
    risk), not merely a cosmetic one. An admin who wants to extract a
    benchmark should use the existing Agent Extraction Panel
    (POST /extraction/jobs), which is a separate, admin-only code path
    with full model choice and no domain-check/quality-floor gating."""
    if user.role != "researcher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only researcher accounts can submit community benchmarks. "
                "Admins should use the Agent Extraction Panel instead."
            ),
        )
    return user
