from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.orm import Benchmark, EvalMetric
from app.schemas.eval_metric import (
    EvalMetricCreate,
    EvalMetricOut,
    EvalMetricUpdate,
    MetricsCompleteness,
)

router = APIRouter(tags=["metrics"])


def _get_benchmark_or_404(db: Session, benchmark_id: UUID) -> Benchmark:
    benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Parent benchmark not found")
    return benchmark


def _get_metric_or_404(db: Session, metric_id: UUID) -> EvalMetric:
    metric = db.query(EvalMetric).filter(EvalMetric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="Eval metric not found")
    return metric


def _normalize_metric_name(name: str) -> str:
    """Strip trailing parenthetical abbreviations and punctuation so naming
    drift (e.g. "relative decision bias (LLM-RDT)" vs. "relative decision
    bias") does not falsely flag a metric as missing. Mirrors the fuzzy
    reconciliation already used server-side during agent extraction.
    """
    name = name.strip()
    paren_idx = name.find("(")
    if paren_idx != -1:
        name = name[:paren_idx].strip()
    return name.rstrip(".,;:").strip().lower()


@router.get("/benchmarks/{benchmark_id}/metrics", response_model=list[EvalMetricOut])
def list_metrics_for_benchmark(benchmark_id: UUID, db: Session = Depends(get_db)):
    _get_benchmark_or_404(db, benchmark_id)
    return (
        db.query(EvalMetric)
        .filter(EvalMetric.benchmark_id == benchmark_id)
        .order_by(EvalMetric.metric_name)
        .all()
    )


@router.get(
    "/benchmarks/{benchmark_id}/metrics/completeness",
    response_model=MetricsCompleteness,
)
def check_metrics_completeness(benchmark_id: UUID, db: Session = Depends(get_db)):
    """Flags any metric name listed in the benchmark's evaluation_metrics
    field that has no corresponding eval_metrics catalogue row. Read-only,
    intended to render as a warning banner on the benchmark edit page.
    """
    benchmark = _get_benchmark_or_404(db, benchmark_id)

    catalogued = {
        _normalize_metric_name(m.metric_name)
        for m in db.query(EvalMetric).filter(EvalMetric.benchmark_id == benchmark_id).all()
    }

    missing = [
        name
        for name in (benchmark.evaluation_metrics or [])
        if _normalize_metric_name(name) not in catalogued
    ]

    return MetricsCompleteness(
        benchmark_id=benchmark_id,
        missing_metric_names=missing,
        is_complete=len(missing) == 0,
    )


@router.post(
    "/benchmarks/{benchmark_id}/metrics",
    response_model=EvalMetricOut,
    status_code=201,
)
def create_metric(
    benchmark_id: UUID,
    payload: EvalMetricCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    _get_benchmark_or_404(db, benchmark_id)

    if payload.benchmark_id != benchmark_id:
        raise HTTPException(
            status_code=400,
            detail="benchmark_id in payload must match the URL path benchmark_id",
        )

    obj = EvalMetric(**payload.model_dump())
    db.add(obj)
    db.flush()

    log_action(
        db, table_name="eval_metrics", record_id=obj.id, action="create",
        changed_by=current_user.id, diff=payload.model_dump(),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/metrics/{metric_id}", response_model=EvalMetricOut)
def get_metric(metric_id: UUID, db: Session = Depends(get_db)):
    return _get_metric_or_404(db, metric_id)


@router.patch("/metrics/{metric_id}", response_model=EvalMetricOut)
def update_metric(
    metric_id: UUID,
    payload: EvalMetricUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = _get_metric_or_404(db, metric_id)

    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(obj, field) for field in changes}

    for field, value in changes.items():
        setattr(obj, field, value)

    log_action(
        db, table_name="eval_metrics", record_id=obj.id, action="update",
        changed_by=current_user.id, diff={"before": before, "after": changes},
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/metrics/{metric_id}", status_code=204)
def delete_metric(
    metric_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    obj = _get_metric_or_404(db, metric_id)

    log_action(
        db, table_name="eval_metrics", record_id=obj.id, action="delete",
        changed_by=current_user.id,
        diff={"metric_name": obj.metric_name, "benchmark_id": str(obj.benchmark_id)},
    )
    db.delete(obj)
    db.commit()
