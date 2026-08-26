# Destination path: backend/app/main.py
# Replaces the existing file in full.
#
# CHANGES (Phase 5 gap closure, this session):
# Wires up the slowapi rate limiter defined in app/core/rate_limit.py:
# app.state.limiter holds the Limiter instance (required by slowapi's
# @limiter.limit(...) decorators used in benchmarks.py, export.py,
# repo_stats.py, and stats.py), the RateLimitExceeded exception handler
# returns a clean 429 instead of an unhandled exception, and
# SlowAPIMiddleware enforces the limiter's default_limits globally so
# every route -- including ones not individually decorated -- gets a
# baseline rate limit. No router registration, CORS config, or the
# /health endpoint changed.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import audit, auth, benchmarks, complexity, export, extraction, metrics, stats, vocab, repo_stats

app = FastAPI(
    title="AISafetyBenchExplorer API",
    version="0.4.0",
    description="Phase 5: researcher dashboard, public read-only API, rate limiting on public endpoints.",
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


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
