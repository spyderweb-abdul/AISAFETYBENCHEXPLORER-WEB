from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import audit, auth, benchmarks, complexity, export, metrics, vocab

app = FastAPI(
    title="AISafetyBenchExplorer API",
    version="0.2.0",
    description="Phase 2: Admin CRUD, complexity auto-classification, audit logging, Excel export.",
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


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
