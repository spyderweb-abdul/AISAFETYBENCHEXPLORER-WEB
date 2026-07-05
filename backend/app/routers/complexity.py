from fastapi import APIRouter, Depends

from app.core.complexity_classifier import ComplexitySignals, classify
from app.core.deps import get_current_user
from app.schemas.complexity import ComplexityResultOut, ComplexitySignalsIn

router = APIRouter(prefix="/complexity", tags=["complexity"])


@router.post("/classify", response_model=ComplexityResultOut)
def classify_benchmark(payload: ComplexitySignalsIn, current_user=Depends(get_current_user)):
    signals = ComplexitySignals(**payload.model_dump())
    level, justification = classify(signals)
    return ComplexityResultOut(complexity_level=level, justification=justification)
