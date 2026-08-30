# Destination path: backend/app/schemas/model_catalog.py
# New file.
#
# Schemas for the admin-manageable ModelOption catalogue (see
# app/models/orm.py's ModelOption). Kept in its own file rather than
# appended to benchmark.py/submission.py since it is unrelated to the
# benchmark/submission domain -- this is platform configuration, not
# catalogue data.

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# agent_runner.py's run_extraction() only dispatches these three
# providers (see the provider == "openai"/"anthropic"/"ollama" branch
# in _call_openai/_call_anthropic/_call_ollama). Keep this set in sync
# with that dispatch if a new provider is ever added there.
ALLOWED_PROVIDERS = {"openai", "anthropic", "ollama"}


class ModelOptionBase(BaseModel):
    identifier: str = Field(
        ..., min_length=3, max_length=100,
        description="Provider-prefixed model id passed as model_used, e.g. openai/gpt-4o",
    )
    provider: str = Field(..., description=f"One of: {sorted(ALLOWED_PROVIDERS)}")
    display_name: Optional[str] = Field(None, max_length=150)
    is_active: bool = True
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("identifier")
    @classmethod
    def _validate_identifier_format(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError(
                "identifier must be in 'provider/model' form, e.g. openai/gpt-4o "
                "-- agent_runner.py splits on '/' to route the call."
            )
        return v

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        if v not in ALLOWED_PROVIDERS:
            raise ValueError(
                f"provider must be one of {sorted(ALLOWED_PROVIDERS)} -- "
                "agent_runner.py's run_extraction() has no dispatch branch "
                "for any other provider and would raise 'Unknown model "
                "provider' at extraction time."
            )
        return v


class ModelOptionCreate(ModelOptionBase):
    pass


class ModelOptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: Optional[str] = Field(None, min_length=3, max_length=100)
    provider: Optional[str] = None
    display_name: Optional[str] = Field(None, max_length=150)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("identifier")
    @classmethod
    def _validate_identifier_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and "/" not in v:
            raise ValueError("identifier must be in 'provider/model' form, e.g. openai/gpt-4o")
        return v

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_PROVIDERS:
            raise ValueError(f"provider must be one of {sorted(ALLOWED_PROVIDERS)}")
        return v


class ModelOptionOut(ModelOptionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
