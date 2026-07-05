from uuid import UUID
from sqlalchemy.orm import Session
from app.models.orm import AuditLog
from fastapi.encoders import jsonable_encoder
import json

def _serialize(value):
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def log_action(
    db: Session,
    table_name: str,
    record_id: UUID,
    action: str,
    changed_by: UUID | None,
    diff: dict | None = None,
) -> None:
    safe_diff = {k: _serialize(v) for k, v in (diff or {}).items()}
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        changed_by=changed_by,
        diff=json.dumps(jsonable_encoder(safe_diff)),
    )
    db.add(entry)
