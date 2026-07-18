from uuid import UUID
from sqlalchemy.orm import Session
from app.models.orm import AuditLog
from fastapi.encoders import jsonable_encoder


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
    """Write an audit_log row for a create/update/delete action.

    IMPORTANT: diff must be passed to the AuditLog ORM object as a plain
    dict, NOT a json.dumps() string. AuditLog.diff is a Postgres JSONB
    column (see models/orm.py); SQLAlchemy's JSONB type already handles
    serialization on bind. Calling json.dumps() here double-encodes the
    value -- Postgres ends up storing a JSON string containing an escaped
    JSON string instead of a real JSON object, which silently breaks
    reads on the /audit-log page (AuditLogOut.diff expects a dict, not a
    string). jsonable_encoder() alone is sufficient: it converts date,
    UUID, and Enum values into JSON-safe primitives (dict/list/str/int/etc)
    while keeping the result a plain Python dict for JSONB to serialize.
    """
    safe_diff = {k: _serialize(v) for k, v in (diff or {}).items()}
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        changed_by=changed_by,
        diff=jsonable_encoder(safe_diff),
    )
    db.add(entry)
