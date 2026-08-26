# Destination path: backend/app/routers/export.py
# Replaces the existing file in full.
#
# CHANGES (Phase 5 gap closure, this session):
# 1. The workbook-building logic used by the existing admin-only
#    GET /export/xlsx is factored into _build_workbook(db, published_only)
#    so it can be reused without duplicating the Sheet 1 / Sheet 2 loop.
# 2. New GET /export/public/xlsx: same template-compatible Excel export,
#    but with no auth dependency and hard-filtered to status="published"
#    benchmarks only, so it is safe to expose on the public researcher
#    dashboard (/browse) without leaking pending_review or rejected
#    extraction attempts. Closes the roadmap gap: "the existing
#    /export/xlsx endpoint is admin-only per Phase 2, not yet exposed
#    on the public dashboard."
# 3. New GET /export/public/csv: a flat, single-sheet CSV of the Sheet 1
#    (Safety Evaluation Benchmarks) fields only, for consumers who want
#    a lightweight tabular export rather than the full two-sheet
#    workbook. Also published-only, no auth.
# 4. Both new public routes carry an explicit slowapi rate limit
#    (10/minute) since regenerating the workbook/CSV on every request
#    is more expensive than a simple list query -- see
#    app/core/rate_limit.py and Known Gap item 22.
# The original admin GET /export/xlsx endpoint is unchanged in behavior
# (still exports every benchmark regardless of status, still requires
# a logged-in user via get_current_user).

import csv
import io

import openpyxl
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rate_limit import limiter
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


def _sheet1_row(b: Benchmark) -> list:
    complexity_cell = b.complexity_level
    if b.complexity_justification:
        complexity_cell = f"{b.complexity_level} - {b.complexity_justification}"
    return [
        b.benchmark_name, _join(b.task_type), b.benchmark_paper_title,
        b.release_date.strftime("%Y-%m") if b.release_date else "",
        b.description, b.code_dataset, b.no_of_samples, b.created_by,
        _join(b.entry_modalities), b.dev_purpose, b.license,
        _join(b.evaluation_metrics), complexity_cell, _join(b.language_support),
        b.integration_option, b.citation_range, b.cited_by,
        b.code_repository, b.dataset_repository, b.benchmark_paper_title, b.paper_link,
    ]


def _build_workbook(db: Session, published_only: bool) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()

    sheet1 = wb.active
    sheet1.title = "Safety Evaluation Benchmarks"
    sheet1.append(SHEET1_HEADERS)

    q = db.query(Benchmark)
    if published_only:
        q = q.filter(Benchmark.status == "published")
    benchmarks = q.order_by(Benchmark.benchmark_name).all()
    for b in benchmarks:
        sheet1.append(_sheet1_row(b))

    sheet2 = wb.create_sheet("Evaluation Metrics Catalogue")
    sheet2.append(SHEET2_HEADERS)

    metrics_q = db.query(EvalMetric)
    if published_only:
        metrics_q = metrics_q.join(Benchmark, EvalMetric.benchmark_id == Benchmark.id).filter(
            Benchmark.status == "published"
        )
    for m in metrics_q.all():
        sheet2.append([
            m.benchmark_name, m.paper_title, m.paper_link, m.metric_name,
            m.conceptual_description, m.methodological_details,
            m.mathematical_definition, m.differences_from_standard_definition, m.notes,
        ])

    return wb


@router.get("/xlsx")
def export_xlsx(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    wb = _build_workbook(db, published_only=False)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=AISafetyBenchExplorer_export.xlsx"},
    )


@router.get("/public/xlsx")
@limiter.limit("10/minute")
def export_public_xlsx(request: Request, db: Session = Depends(get_db)):
    """Phase 5: public, unauthenticated, template-compatible Excel
    export scoped to status="published" benchmarks only. Intended for
    the /browse researcher dashboard's export button."""
    wb = _build_workbook(db, published_only=True)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=AISafetyBenchExplorer_published.xlsx"},
    )


@router.get("/public/csv")
@limiter.limit("10/minute")
def export_public_csv(request: Request, db: Session = Depends(get_db)):
    """Phase 5: public, unauthenticated, flat single-sheet CSV of the
    Safety Evaluation Benchmarks fields only, scoped to
    status="published" benchmarks. Lighter alternative to the full
    two-sheet workbook for consumers that only want Sheet 1 data."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(SHEET1_HEADERS)

    benchmarks = (
        db.query(Benchmark)
        .filter(Benchmark.status == "published")
        .order_by(Benchmark.benchmark_name)
        .all()
    )
    for b in benchmarks:
        writer.writerow(_sheet1_row(b))

    byte_buffer = io.BytesIO(buffer.getvalue().encode("utf-8"))
    byte_buffer.seek(0)

    return StreamingResponse(
        byte_buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=AISafetyBenchExplorer_published.csv"},
    )
