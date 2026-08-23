from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import audit, auth, benchmarks, complexity, export, extraction, metrics, stats, vocab, repo_stats

app = FastAPI(
    title="AISafetyBenchExplorer API",
    version="0.3.0",
    description="Phase 3: Agent Orchestration Layer - extraction jobs, agent runner, pending review inbox.",
)

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
