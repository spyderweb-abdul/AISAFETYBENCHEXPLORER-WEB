import io

import openpyxl
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.orm import Benchmark, EvalMetric

router = APIRouter(prefix="/export", tags=["export"])

SHEET1_HEADERS = [
    "Benchmark Name", "Task Type", "Benchmark Paper Title", "Release",
    "Description", "Code / Dataset", "No. of Samples", "Created By",
    "Entry Modalities", "Dev Purpose", "License", "Evaluation Metrics",
    "Complexity Level", "Language Support", "Integration Option",
    "Citation Range", "Cited By", "Code Repository", "Dataset Repository",
    "Benchmark Paper", "Paper Link",
]

SHEET2_HEADERS = [
    "benchmark_name", "paper_title", "paper_link", "metric_name",
    "conceptual_description", "methodological_details",
    "mathematical_definition", "differences_from_standard_definition",
    "notes",
]


def _join(values: list[str]) -> str:
    return ", ".join(values) if values else ""


@router.get("/xlsx")
def export_xlsx(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    wb = openpyxl.Workbook()

    sheet1 = wb.active
    sheet1.title = "Safety Evaluation Benchmarks"
    sheet1.append(SHEET1_HEADERS)

    benchmarks = db.query(Benchmark).order_by(Benchmark.benchmark_name).all()
    for b in benchmarks:
        complexity_cell = b.complexity_level
        if b.complexity_justification:
            complexity_cell = f"{b.complexity_level} - {b.complexity_justification}"

        sheet1.append([
            b.benchmark_name, _join(b.task_type), b.benchmark_paper_title,
            b.release_date.strftime("%Y-%m") if b.release_date else "",
            b.description, b.code_dataset, b.no_of_samples, b.created_by,
            _join(b.entry_modalities), b.dev_purpose, b.license,
            _join(b.evaluation_metrics), complexity_cell, _join(b.language_support),
            b.integration_option, b.citation_range, b.cited_by,
            b.code_repository, b.dataset_repository, b.benchmark_paper_title, b.paper_link,
        ])

    sheet2 = wb.create_sheet("Evaluation Metrics Catalogue")
    sheet2.append(SHEET2_HEADERS)

    metrics = db.query(EvalMetric).all()
    for m in metrics:
        sheet2.append([
            m.benchmark_name, m.paper_title, m.paper_link, m.metric_name,
            m.conceptual_description, m.methodological_details,
            m.mathematical_definition, m.differences_from_standard_definition, m.notes,
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=AISafetyBenchExplorer_export.xlsx"},
    )
