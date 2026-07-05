"""
Phase 1 one-time migration script.
Reads the existing "Copy of AISafetyBenchExplorer.xlsx" workbook and loads
Sheet 1 (Safety Evaluation Benchmarks) and Sheet 2 (Evaluation Metrics
Catalogue) into the new PostgreSQL schema via SQLAlchemy.

Usage:
    python scripts/migrate_excel_to_db.py --file "Copy of AISafetyBenchExplorer.xlsx"
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models.orm import Benchmark, EvalMetric  # noqa: E402

SHEET1_NAME = "Safety Evaluation Benchmarks"
SHEET2_NAME = "Evaluation Metrics Catalogue"

SHEET1_COLUMN_MAP = {
    "Benchmark Name": "benchmark_name",
    "Task Type": "task_type",
    "Benchmark Paper Title": "benchmark_paper_title",
    "Release": "release_date",
    "Description": "description",
    "Code / Dataset": "code_dataset",
    "No. of Samples": "no_of_samples",
    "Created By": "created_by",
    "Entry Modalities": "entry_modalities",
    "Dev Purpose": "dev_purpose",
    "License": "license",
    "Evaluation Metrics": "evaluation_metrics",
    "Complexity Level": "complexity_level_raw",
    "Language Support": "language_support",
    "Integration Option": "integration_option",
    "Citation Range": "citation_range",
    "Cited By": "cited_by",
    "Code Repository": "code_repository",
    "Dataset Repository": "dataset_repository",
    "Paper Link": "paper_link",
}

SHEET2_COLUMN_MAP = {
    "benchmark_name": "benchmark_name",
    "paper_title": "paper_title",
    "paper_link": "paper_link",
    "metric_name": "metric_name",
    "conceptual_description": "conceptual_description",
    "methodological_details": "methodological_details",
    "mathematical_definition": "mathematical_definition",
    "differences_from_standard_definition": "differences_from_standard_definition",
    "notes": "notes",
}


def split_multivalue(cell) -> list[str]:
    if pd.isna(cell):
        return []
    return [v.strip() for v in str(cell).split(",") if v.strip()]


def parse_complexity(raw) -> tuple[str, str]:
    if pd.isna(raw):
        return "Unknown", None
    text = str(raw)
    for level in ["Popular", "High", "Medium", "Low"]:
        if text.strip().lower().startswith(level.lower()):
            parts = text.split("-", 1)
            justification = parts[1].strip() if len(parts) > 1 else None
            return level, justification
    return "Unknown", text


def migrate_sheet1(xlsx_path: Path, db: Session) -> dict[str, str]:
    df = pd.read_excel(xlsx_path, sheet_name=SHEET1_NAME)
    df = df.rename(columns=SHEET1_COLUMN_MAP)

    name_to_id: dict[str, str] = {}

    for _, row in df.iterrows():
        complexity_level, justification = parse_complexity(row.get("complexity_level_raw"))

        obj = Benchmark(
            benchmark_name=str(row.get("benchmark_name", "")).strip(),
            task_type=split_multivalue(row.get("task_type")),
            benchmark_paper_title=str(row.get("benchmark_paper_title", "")).strip(),
            release_date=pd.to_datetime(row.get("release_date"), errors="coerce"),
            description=row.get("description"),
            code_dataset="Yes" if str(row.get("code_dataset", "")).strip().lower() == "yes" else "No",
            no_of_samples=row.get("no_of_samples"),
            created_by=row.get("created_by") if row.get("created_by") in ("Human", "Machine", "Hybrid") else None,
            entry_modalities=split_multivalue(row.get("entry_modalities")),
            dev_purpose=row.get("dev_purpose") if row.get("dev_purpose") in ("Eval", "Train", "Train & Eval") else None,
            license=row.get("license"),
            evaluation_metrics=split_multivalue(row.get("evaluation_metrics")),
            complexity_level=complexity_level,
            complexity_justification=justification,
            language_support=split_multivalue(row.get("language_support")),
            integration_option=row.get("integration_option") if row.get("integration_option") in ("API", "Export", "API & Export") else "NA",
            citation_range=row.get("citation_range"),
            cited_by=int(row.get("cited_by")) if not pd.isna(row.get("cited_by")) else 0,
            code_repository=row.get("code_repository"),
            dataset_repository=row.get("dataset_repository"),
            paper_link=row.get("paper_link"),
        )
        db.add(obj)
        db.flush()
        name_to_id[obj.benchmark_name] = obj.id

    db.commit()
    print(f"Migrated {len(name_to_id)} benchmark records from {SHEET1_NAME}.")
    return name_to_id


def migrate_sheet2(xlsx_path: Path, db: Session, name_to_id: dict[str, str]) -> None:
    df = pd.read_excel(xlsx_path, sheet_name=SHEET2_NAME)
    df = df.rename(columns=SHEET2_COLUMN_MAP)

    inserted, skipped = 0, 0
    for _, row in df.iterrows():
        benchmark_name = str(row.get("benchmark_name", "")).strip()
        benchmark_id = name_to_id.get(benchmark_name)
        if not benchmark_id:
            skipped += 1
            continue

        obj = EvalMetric(
            benchmark_id=benchmark_id,
            benchmark_name=benchmark_name,
            paper_title=row.get("paper_title"),
            paper_link=row.get("paper_link"),
            metric_name=row.get("metric_name"),
            conceptual_description=row.get("conceptual_description"),
            methodological_details=row.get("methodological_details"),
            mathematical_definition=row.get("mathematical_definition"),
            differences_from_standard_definition=row.get("differences_from_standard_definition"),
            notes=row.get("notes"),
        )
        db.add(obj)
        inserted += 1

    db.commit()
    print(f"Migrated {inserted} metric records from {SHEET2_NAME}. Skipped {skipped} (no matching benchmark).")


def main():
    parser = argparse.ArgumentParser(description="Migrate the AISafetyBenchExplorer workbook into PostgreSQL.")
    parser.add_argument("--file", required=True, help="Path to the .xlsx workbook")
    args = parser.parse_args()

    xlsx_path = Path(args.file)
    if not xlsx_path.exists():
        raise SystemExit(f"File not found: {xlsx_path}")

    db = SessionLocal()
    try:
        name_to_id = migrate_sheet1(xlsx_path, db)
        migrate_sheet2(xlsx_path, db, name_to_id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
