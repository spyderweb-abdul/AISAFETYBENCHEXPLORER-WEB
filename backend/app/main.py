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
    paper_metadata,
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
app.include_router(paper_metadata.router)
app.include_router(stats.router)
app.include_router(submissions.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.include_router(models.router)
app.include_router(vocab_terms.router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
