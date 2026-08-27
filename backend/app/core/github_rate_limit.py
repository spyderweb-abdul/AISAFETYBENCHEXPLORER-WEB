from __future__ import annotations

from datetime import datetime, timezone

import httpx

_RATE_LIMIT_URL = "https://api.github.com/rate_limit"


def check_github_rate_limit(github_token: str) -> dict:
    """Returns {'limit': int, 'remaining': int, 'reset_at': iso str,
    'authenticated': bool} for the GitHub REST API's 'core' rate-limit
    category (the category used by github_scrapper.py's repo/commit/
    contributor lookups).

    An empty github_token still produces a valid response -- GitHub
    applies a 60 req/hour ceiling to unauthenticated requests, which is
    exactly the ceiling this project already hit once during Phase 4
    testing (see PROJECT_ROADMAP.md's 2026-07-26 Change Log)."""
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    response = httpx.get(_RATE_LIMIT_URL, headers=headers, timeout=10)
    response.raise_for_status()
    core = response.json()["resources"]["core"]
    return {
        "limit": core["limit"],
        "remaining": core["remaining"],
        "reset_at": datetime.fromtimestamp(core["reset"], tz=timezone.utc).isoformat(),
        "authenticated": bool(github_token),
    }


def has_sufficient_quota(
    github_token: str, estimated_requests_needed: int, safety_margin: int = 20
) -> tuple[bool, dict]:
    """Returns (True, status) if there is enough remaining quota for
    estimated_requests_needed plus a small safety_margin buffer (to
    leave headroom for other concurrent usage -- e.g. an admin manually
    refreshing one benchmark while a bulk job is also queued);
    (False, status) otherwise. status is the same dict returned by
    check_github_rate_limit(), for logging or surfacing to a caller."""
    status = check_github_rate_limit(github_token)
    sufficient = status["remaining"] >= (estimated_requests_needed + safety_margin)
    return sufficient, status
