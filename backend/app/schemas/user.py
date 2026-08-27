# Destination path: backend/app/schemas/user.py
# Replaces the existing file in full.
#
# SECURITY FIX (found and fixed this session, unrelated to but
# discovered while building Phase 6 item 4): UserCreate previously
# declared a client-settable `role: UserRole = UserRole.researcher`
# field, and POST /auth/register (see auth.py) wrote
# role=payload.role.value directly from that field -- meaning ANY
# anonymous caller could self-register as role="admin" simply by
# including that field in the request body. This completely undermines
# the entire gated-submission/admin-review workflow this session is
# building, since "researcher" was never actually an enforced,
# untrusted tier. Fixed by removing `role` from UserCreate entirely;
# app/routers/auth.py now hardcodes role="researcher" on every
# registration regardless of request body. There is intentionally no
# self-service path to becoming an admin -- admin accounts must be
# created directly in the database (as documented in the roadmap's
# Phase 1 verification notes) or via a future dedicated admin-only
# user-management endpoint.
#
# CHANGE (Phase 6 item 4): UserOut gains is_trusted_submitter, so the
# frontend can show a trust badge and the admin user-management view
# (if built later) can display current trust status.

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRole(str, Enum):
    admin = "admin"
    researcher = "researcher"


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    # NOTE: role is deliberately NOT a field here -- see the security
    # fix note above. Every self-registered account is a "researcher"
    # unconditionally; there is no client-controlled way to become an
    # admin through this schema.


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    is_trusted_submitter: bool = False
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
