# Destination path: backend/app/main.py
# Replaces the existing file in full.
#
# CHANGE (2026-09-01): registers the new vocab_terms router (admin CRUD
# for the VocabTerm task_type/evaluation_metric catalogue,
# backend/app/routers/vocab_terms.py). Kept as a separate router import
# name from the existing vocab.py (already registered below) to avoid
# a naming collision -- vocab.py serves the static controlled-vocabulary
# lists for BenchmarkForm.tsx dropdowns; vocab_terms.py serves the new,
# agent-grown, DB-backed catalogue.
#
# CHANGE (2026-08-28): registers the models router (admin CRUD for the
# ModelOption catalogue, backend/app/routers/models.py).
#
# CHANGE (Phase 6 items 3/4, prior session): registers submissions,
# notifications, and users routers.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import (
    audit,
    auth,
    benchmarks,
    complexity,
    export,
    extraction,
    metrics,
    models,
    notifications,
    repo_stats,
    stats,
    submissions,
    users,
    vocab,
    vocab_terms,
)

app = FastAPI(
    title="AISafetyBenchExplorer API",
    version="0.6.0",
    description="Phase 6: gated community submissions, admin review workflow, notifications, admin model catalogue, and DB-backed vocabulary guidance.",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(benchmarks.router)
app.include_router(metrics.router)
app.include_router(complexity.router)
app.include_router(audit.router)
app.include_router(export.router)
app.include_router(vocab.router)
app.include_router(extraction.router)
app.include_router(repo_stats.router)
app.include_router(stats.router)
app.include_router(submissions.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.include_router(models.router)
app.include_router(vocab_terms.router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}