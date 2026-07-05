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
    role: UserRole = UserRole.researcher


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
