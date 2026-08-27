# Destination path: backend/app/routers/auth.py
# Replaces the existing file in full. (Supersedes the earlier draft
# from this same session -- this version adds rate limiting to
# /register, which the earlier draft omitted. Without it, someone
# could mass-create researcher accounts to sidestep the per-user
# consecutive-rejection submission block in submission_runner.py
# entirely, since that guard is keyed on submitter_user_id.)
#
# SECURITY FIX (this session): register() previously wrote
# role=payload.role.value, trusting a client-controlled field on
# UserCreate. Combined with UserCreate declaring
# `role: UserRole = UserRole.researcher` as an OPEN field (not
# restricted server-side), any anonymous caller could self-register as
# role="admin". Fixed two ways: (1) UserCreate no longer has a role
# field at all (see schemas/user.py), and (2) register() now hardcodes
# role="researcher" explicitly here too, so this endpoint is safe even
# if a future schema change accidentally reintroduces a role field on
# UserCreate without updating this function. Admin accounts must be
# created directly in the database -- there is intentionally no
# self-service or API path to becoming an admin.
#
# No other route or behavior in this file changed.

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.orm import User
from app.schemas.user import Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        # SECURITY: hardcoded, not derived from the request body. See
        # the module docstring above.
        role="researcher",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(subject=user.email, role=user.role)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
