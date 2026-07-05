from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.orm import Benchmark
from app.schemas.benchmark import BenchmarkCreate, BenchmarkOut, BenchmarkUpdate

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("", response_model=list[BenchmarkOut])
def list_benchmarks(
    task_type: Optional[str] = Query(None),
    complexity_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Benchmark)
    if task_type:
        q = q.filter(Benchmark.task_type.any(task_type))
    if complexity_level:
        q = q.filter(Benchmark.complexity_level == complexity_level)
    if search:
        q = q.filter(Benchmark.benchmark_name.ilike(f"%{search}%"))
    return q.order_by(Benchmark.benchmark_name).offset(offset).limit(limit).all()


@router.get("/{benchmark_id}", response_model=BenchmarkOut)
def get_benchmark(benchmark_id: UUID, db: Session = Depends(get_db)):
    obj = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return obj


@router.post("", response_model=BenchmarkOut, status_code=201)
def create_benchmark(
    payload: BenchmarkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = Benchmark(**payload.model_dump(), created_by_user_id=current_user.id)
    db.add(obj)
    db.flush()

    log_action(
        db, table_name="benchmarks", record_id=obj.id, action="create",
        changed_by=current_user.id, diff=payload.model_dump(),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{benchmark_id}", response_model=BenchmarkOut)
def update_benchmark(
    benchmark_id: UUID,
    payload: BenchmarkUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(obj, field) for field in changes}

    for field, value in changes.items():
        setattr(obj, field, value)
    obj.updated_by_user_id = current_user.id

    log_action(
        db, table_name="benchmarks", record_id=obj.id, action="update",
        changed_by=current_user.id, diff={"before": before, "after": changes},
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{benchmark_id}", status_code=204)
def delete_benchmark(
    benchmark_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    log_action(
        db, table_name="benchmarks", record_id=obj.id, action="delete",
        changed_by=current_user.id, diff={"benchmark_name": obj.benchmark_name},
    )
    db.delete(obj)
    db.commit()
