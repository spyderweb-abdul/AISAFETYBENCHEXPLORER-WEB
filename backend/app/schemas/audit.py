from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    table_name: str
    record_id: UUID
    action: str
    changed_by: UUID | None
    diff: dict | None
    created_at: datetime
