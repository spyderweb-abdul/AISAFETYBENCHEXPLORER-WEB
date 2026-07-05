from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.orm import Benchmark, EvalMetric
from app.schemas.eval_metric import EvalMetricCreate, EvalMetricOut

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/by-benchmark/{benchmark_id}", response_model=list[EvalMetricOut])
def list_metrics_for_benchmark(benchmark_id: UUID, db: Session = Depends(get_db)):
    return db.query(EvalMetric).filter(EvalMetric.benchmark_id == benchmark_id).all()


@router.post("", response_model=EvalMetricOut, status_code=201)
def create_metric(
    payload: EvalMetricCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    benchmark = db.query(Benchmark).filter(Benchmark.id == payload.benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Parent benchmark not found")

    obj = EvalMetric(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
