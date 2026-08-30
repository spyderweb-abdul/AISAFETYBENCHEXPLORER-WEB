# Destination path: backend/app/routers/models.py
# New file.
#
# Admin CRUD for the ModelOption catalogue (app/models/orm.py). Both
# the Agent Extraction Panel (frontend/app/admin/extraction/page.tsx)
# and the community submissions re-extract dropdown
# (frontend/app/admin/submissions/page.tsx) call GET /models instead of
# importing a hardcoded array, so adding/retiring a model is now an
# admin UI action instead of a code change + redeploy.
#
# All routes are admin-only (require_admin), matching the fact that
# both consumer pages already sit behind the admin section of the app.

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.orm import ModelOption, User
from app.schemas.model_catalog import ModelOptionCreate, ModelOptionOut, ModelOptionUpdate

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelOptionOut])
def list_models(
    active_only: bool = Query(
        True,
        description=(
            "If true (default), only is_active=true rows are returned -- "
            "this is what the extraction/submissions dropdowns should call. "
            "Set false for the admin management page, which needs to see "
            "and re-activate disabled models too."
        ),
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[ModelOption]:
    q = db.query(ModelOption)
    if active_only:
        q = q.filter(ModelOption.is_active.is_(True))
    return q.order_by(ModelOption.provider, ModelOption.identifier).all()


@router.post("", response_model=ModelOptionOut, status_code=status.HTTP_201_CREATED)
def create_model(
    payload: ModelOptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelOption:
    existing = db.query(ModelOption).filter(ModelOption.identifier == payload.identifier).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Model '{payload.identifier}' already exists.")

    model = ModelOption(**payload.model_dump(), created_by_user_id=current_user.id)
    db.add(model)
    db.commit()
    db.refresh(model)

    log_action(
        db, table_name="model_options", record_id=model.id, action="create",
        changed_by=current_user.id, diff=payload.model_dump(),
    )
    db.commit()
    return model


@router.patch("/{model_id}", response_model=ModelOptionOut)
def update_model(
    model_id: uuid.UUID,
    payload: ModelOptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelOption:
    model = db.query(ModelOption).filter(ModelOption.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    updates = payload.model_dump(exclude_unset=True)

    if "identifier" in updates and updates["identifier"] != model.identifier:
        clash = db.query(ModelOption).filter(ModelOption.identifier == updates["identifier"]).first()
        if clash:
            raise HTTPException(status_code=409, detail=f"Model '{updates['identifier']}' already exists.")

    before = {
        "identifier": model.identifier,
        "provider": model.provider,
        "display_name": model.display_name,
        "is_active": model.is_active,
        "notes": model.notes,
    }
    for field, value in updates.items():
        setattr(model, field, value)
    db.commit()
    db.refresh(model)

    log_action(
        db, table_name="model_options", record_id=model.id, action="update",
        changed_by=current_user.id, diff={"before": before, "after": updates},
    )
    db.commit()
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Hard delete. Safe because ExtractionJob.model_used and
    Submission.model_used are plain string columns, not foreign keys to
    model_options.id -- historical job/submission records keep their
    recorded model string regardless of whether this row still exists.
    If you would rather keep a record of retired models, use
    PATCH /models/{id} with is_active=false instead of deleting."""
    model = db.query(ModelOption).filter(ModelOption.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    log_action(
        db, table_name="model_options", record_id=model.id, action="delete",
        changed_by=current_user.id, diff={"identifier": model.identifier, "provider": model.provider},
    )
    db.delete(model)
    db.commit()