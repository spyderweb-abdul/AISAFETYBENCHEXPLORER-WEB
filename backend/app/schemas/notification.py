# Destination path: backend/app/schemas/notification.py
# New file.

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_type: str
    title: str
    body: Optional[str] = None
    link_path: Optional[str] = None
    is_read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    """A single page of a user's personal notification history."""

    items: list[NotificationOut]
    total: int
    page: int
    page_size: int
    total_pages: int
