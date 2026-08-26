# Destination path: backend/app/core/rate_limit.py
# New file.
#
# Phase 5 gap closure (roadmap Known Gap item 22): the public
# read-only endpoints (GET /benchmarks, /benchmarks/{id},
# /benchmarks/{id}/metrics, /repo-stats/benchmarks/{id},
# /stats/research-gap-heatmap, and the new /export/public/xlsx and
# /export/public/csv routes) have no auth dependency and, until now,
# no rate limiting either.
#
# limiter.default_limits is registered globally in main.py via
# app.state.limiter + SlowAPIMiddleware, so every route in the app
# gets this floor automatically, including any router (e.g.
# metrics.py) that is not individually decorated below. Routes that
# are meaningfully more expensive than a simple filtered list query
# (workbook/CSV generation, the heatmap aggregation) carry an explicit,
# tighter @limiter.limit(...) decorator directly on the route function
# -- see benchmarks.py, export.py, repo_stats.py, and stats.py.
#
# Keying is per client IP (get_remote_address). This is an in-memory
# limiter (no Redis backend configured), which is sufficient for a
# single-process MVP deployment; if the API is ever run with multiple
# worker processes behind a load balancer, switch storage_uri to the
# existing Redis instance (already used by Celery) so limits are
# shared across processes instead of being enforced per-process.

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
