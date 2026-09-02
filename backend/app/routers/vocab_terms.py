from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.orm import User, VocabTerm
from app.schemas.vocab_term import VocabTermCreate, VocabTermOut, VocabTermUpdate

router = APIRouter(prefix="/vocab-terms", tags=["vocab-terms"])


@router.get("", response_model=list[VocabTermOut])
def list_vocab_terms(
    category: str | None = Query(None, description="Filter to 'task_type' or 'evaluation_metric'"),
    active_only: bool = Query(
        True,
        description=(
            "If true (default), only is_active=true rows are returned -- "
            "this is what agent_runner.py's prompt-guidance fetch and any "
            "dropdown (including the public /browse Task Type filter) "
            "should call. Set false for the admin management page, which "
            "needs to see and re-activate disabled terms too."
        ),
    ),
    canonical_only: bool = Query(
        False,
        description="If true, exclude terms marked as an alias of another (is_canonical=false).",
    ),
    unreviewed_only: bool = Query(
        False,
        description="If true, only return source='agent' terms -- for an admin triage view of recently auto-added terms.",
    ),
    db: Session = Depends(get_db),
) -> list[VocabTerm]:
    """Public read, matching GET /vocab's access model -- both the
    admin catalogue management page and the public /browse filter
    dropdown call this same endpoint. unreviewed_only is harmless to
    leave publicly queryable (it only reveals term provenance, not any
    sensitive data), but in practice only the admin UI passes it."""
    q = db.query(VocabTerm)
    if category:
        q = q.filter(VocabTerm.category == category)
    if active_only:
        q = q.filter(VocabTerm.is_active.is_(True))
    if canonical_only:
        q = q.filter(VocabTerm.is_canonical.is_(True))
    if unreviewed_only:
        q = q.filter(VocabTerm.source == "agent")
    return q.order_by(VocabTerm.category, VocabTerm.usage_count.desc()).all()


@router.post("", response_model=VocabTermOut, status_code=status.HTTP_201_CREATED)
def create_vocab_term(
    payload: VocabTermCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> VocabTerm:
    from app.core.vocab_normalize import normalize_term  # local import, see note in that module

    normalized = normalize_term(payload.term)
    existing = (
        db.query(VocabTerm)
        .filter(VocabTerm.category == payload.category, VocabTerm.normalized_term == normalized)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Term '{payload.term}' already exists in category '{payload.category}' (as '{existing.term}').",
        )

    term = VocabTerm(
        category=payload.category,
        term=payload.term,
        normalized_term=normalized,
        is_active=payload.is_active,
        is_canonical=payload.is_canonical,
        canonical_term_id=payload.canonical_term_id,
        source="admin",
        usage_count=1,
    )
    db.add(term)
    db.commit()
    db.refresh(term)

    log_action(
        db, table_name="vocab_terms", record_id=term.id, action="create",
        changed_by=current_user.id, diff=payload.model_dump(mode="json"),
    )
    db.commit()
    return term


@router.patch("/{term_id}", response_model=VocabTermOut)
def update_vocab_term(
    term_id: uuid.UUID,
    payload: VocabTermUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> VocabTerm:
    from app.core.vocab_normalize import normalize_term

    term = db.query(VocabTerm).filter(VocabTerm.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Vocab term not found")

    updates = payload.model_dump(exclude_unset=True)

    if "term" in updates and updates["term"] != term.term:
        new_normalized = normalize_term(updates["term"])
        clash = (
            db.query(VocabTerm)
            .filter(
                VocabTerm.category == term.category,
                VocabTerm.normalized_term == new_normalized,
                VocabTerm.id != term.id,
            )
            .first()
        )
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"Another term '{clash.term}' already normalizes to the same value.",
            )
        term.normalized_term = new_normalized

    before = {
        "term": term.term,
        "is_active": term.is_active,
        "is_canonical": term.is_canonical,
        "canonical_term_id": str(term.canonical_term_id) if term.canonical_term_id else None,
    }
    for field, value in updates.items():
        setattr(term, field, value)
    db.commit()
    db.refresh(term)

    log_action(
        db, table_name="vocab_terms", record_id=term.id, action="update",
        changed_by=current_user.id, diff={"before": before, "after": updates},
    )
    db.commit()
    return term


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vocab_term(
    term_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Hard delete. Safe because Benchmark.task_type and
    Benchmark.evaluation_metrics are plain ARRAY(Text) columns, not
    foreign keys to vocab_terms.id -- deleting a term never changes any
    existing benchmark row. Prefer PATCH with is_active=false if you
    just want to stop suggesting a term without losing its history."""
    term = db.query(VocabTerm).filter(VocabTerm.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Vocab term not found")

    log_action(
        db, table_name="vocab_terms", record_id=term.id, action="delete",
        changed_by=current_user.id, diff={"category": term.category, "term": term.term},
    )
    db.delete(term)
    db.commit()
