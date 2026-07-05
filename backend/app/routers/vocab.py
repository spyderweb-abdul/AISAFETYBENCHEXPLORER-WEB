from fastapi import APIRouter

from app.core import controlled_vocab as cv

router = APIRouter(prefix="/vocab", tags=["vocab"])


@router.get("")
def get_all_vocab():
    return {
        "task_type": cv.KNOWN_TASK_TYPES,
        "entry_modalities": cv.ENTRY_MODALITIES,
        "created_by": cv.CREATED_BY,
        "dev_purpose": cv.DEV_PURPOSE,
        "integration_option": cv.INTEGRATION_OPTION,
        "complexity_level": cv.COMPLEXITY_LEVEL,
        "code_dataset": cv.CODE_DATASET,
        "use_cases": cv.USE_CASES,
        "language_support": cv.LANGUAGE_SUPPORT
    }
