# Destination path: backend/app/main.py
# Replaces the existing file in full.

# CHANGE (2026-08-28): registers the new models router (admin CRUD for
# the ModelOption catalogue, backend/app/routers/models.py), so the
# Agent Extraction Panel and community submissions re-extract dropdown
# can be admin-managed from the DB instead of hardcoded frontend
# arrays. This supersedes the earlier main_py_router_registration_patch.md
# guess -- that patch assumed a shorter router list than this file
# actually has (it did not know about repo_stats, stats, or users).
#
# CHANGE (Phase 6 items 3/4, prior session): registers three routers --
# submissions (gated community submission workflow), notifications
# (per-user in-app inbox), and users (minimal admin-only user
# management, needed for the is_trusted_submitter toggle). No other
# router, middleware, or the /health endpoint changed.

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
)

app = FastAPI(
    title="AISafetyBenchExplorer API",
    version="0.5.0",
    description="Phase 6: gated community submissions, admin review workflow, and notifications.",
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


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
