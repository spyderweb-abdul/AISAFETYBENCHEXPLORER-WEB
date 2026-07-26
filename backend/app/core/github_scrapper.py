"""
github_scrapper.py

Deterministic GitHub repository activity scraper for AISafetyBenchExplorer-Web.
Closes Known Gap 10 (Phase 3): replaces the agent's own agentic web_search
calls for GitHub metadata with a real, auditable, rate-limit-aware HTTP tool.

Feeds repo_stats (FK to benchmarks), which in turn feeds the Popular/High/
Medium/Low complexity thresholds defined in complexity-methodology.md:
    Popular: >200 stars, active community
    High:    30-150 stars, multiple contributors
    Medium:  20-100 stars, growing community
    Low:     <20 stars or no active development

Usage as a deterministic tool (called by agent_runner.py during Phase 0.2,
or by the Celery Beat scheduled refresh task in tasks.py):

    from app.core.github_scrapper import fetch_github_stats
    stats = fetch_github_stats("https://github.com/owner/repo")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
REPO_URL_PATTERN = re.compile(
    r"github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$"
)


@dataclass
class GitHubRepoStats:
    owner: str
    repo: str
    stars: int
    forks: int
    open_issues: int
    contributors_count: Optional[int]
    last_commit_at: Optional[datetime]
    is_archived: bool
    license_spdx: Optional[str]
    days_since_last_commit: Optional[int]
    activity_status: str
    fetched_at: datetime
    error: Optional[str] = None


def parse_github_url(url: str) -> Optional[tuple[str, str]]:
    match = REPO_URL_PATTERN.search(url.strip())
    if not match:
        return None
    return match.group("owner"), match.group("repo")


def _is_retryable_http_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 403 and exc.response.headers.get("X-RateLimit-Remaining") == "0":
            return True
        if status in (429, 500, 502, 503, 504):
            return True
    return False


class GitHubScrapper:
    """
    Thin, deterministic wrapper around the GitHub REST API.
    Every numeric/date field returned here is reproducible and auditable,
    per Section 2 of PROJECT_ROADMAP.md's Agent-as-Orchestrator architecture.
    """

    def __init__(self, github_token: Optional[str] = None, timeout: float = 10.0):
        headers = {"Accept": "application/vnd.github+json"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        self._client = httpx.Client(
            base_url=GITHUB_API_BASE, headers=headers, timeout=timeout
        )

    def close(self) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception(_is_retryable_http_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        response = self._client.get(path, params=params)
        if response.status_code == 404:
            return response
        response.raise_for_status()
        return response

    def fetch_repo_stats(self, repo_url: str) -> GitHubRepoStats:
        parsed = parse_github_url(repo_url)
        now = datetime.now(timezone.utc)

        if parsed is None:
            logger.warning("github_scrapper: unparseable repo URL %r", repo_url)
            return GitHubRepoStats(
                owner="",
                repo="",
                stars=0,
                forks=0,
                open_issues=0,
                contributors_count=None,
                last_commit_at=None,
                is_archived=False,
                license_spdx=None,
                days_since_last_commit=None,
                activity_status="unknown",
                fetched_at=now,
                error="unparseable_url",
            )

        owner, repo = parsed

        try:
            repo_resp = self._get(f"/repos/{owner}/{repo}")
        except httpx.HTTPError as exc:
            logger.error("github_scrapper: repo fetch failed for %s/%s: %s", owner, repo, exc)
            return GitHubRepoStats(
                owner=owner,
                repo=repo,
                stars=0,
                forks=0,
                open_issues=0,
                contributors_count=None,
                last_commit_at=None,
                is_archived=False,
                license_spdx=None,
                days_since_last_commit=None,
                activity_status="unknown",
                fetched_at=now,
                error=f"repo_fetch_failed: {exc}",
            )

        if repo_resp.status_code == 404:
            return GitHubRepoStats(
                owner=owner,
                repo=repo,
                stars=0,
                forks=0,
                open_issues=0,
                contributors_count=None,
                last_commit_at=None,
                is_archived=False,
                license_spdx=None,
                days_since_last_commit=None,
                activity_status="not_found",
                fetched_at=now,
                error="repo_not_found",
            )

        repo_data = repo_resp.json()

        last_commit_at: Optional[datetime] = None
        try:
            commits_resp = self._get(f"/repos/{owner}/{repo}/commits", params={"per_page": 1})
            if commits_resp.status_code == 200:
                commits = commits_resp.json()
                if commits:
                    raw_date = commits[0]["commit"]["committer"]["date"]
                    last_commit_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except httpx.HTTPError as exc:
            logger.warning("github_scrapper: commit lookup failed for %s/%s: %s", owner, repo, exc)

        contributors_count: Optional[int] = None
        try:
            contrib_resp = self._get(
                f"/repos/{owner}/{repo}/contributors",
                params={"per_page": 1, "anon": "true"},
            )
            if contrib_resp.status_code == 200:
                link_header = contrib_resp.headers.get("Link", "")
                last_page_match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if last_page_match:
                    contributors_count = int(last_page_match.group(1))
                else:
                    contributors_count = len(contrib_resp.json())
        except httpx.HTTPError as exc:
            logger.warning("github_scrapper: contributors lookup failed for %s/%s: %s", owner, repo, exc)

        days_since_last_commit: Optional[int] = None
        if last_commit_at is not None:
            days_since_last_commit = (now - last_commit_at).days

        is_archived = bool(repo_data.get("archived", False))
        if is_archived:
            activity_status = "archived"
        elif days_since_last_commit is None:
            activity_status = "unknown"
        elif days_since_last_commit <= 90:
            activity_status = "active"
        elif days_since_last_commit <= 365:
            activity_status = "slowing"
        else:
            activity_status = "stale"

        license_info = repo_data.get("license") or {}

        return GitHubRepoStats(
            owner=owner,
            repo=repo,
            stars=repo_data.get("stargazers_count", 0),
            forks=repo_data.get("forks_count", 0),
            open_issues=repo_data.get("open_issues_count", 0),
            contributors_count=contributors_count,
            last_commit_at=last_commit_at,
            is_archived=is_archived,
            license_spdx=license_info.get("spdx_id"),
            days_since_last_commit=days_since_last_commit,
            activity_status=activity_status,
            fetched_at=now,
            error=None,
        )


def fetch_github_stats(repo_url: str, github_token: Optional[str] = None) -> GitHubRepoStats:
    """
    Convenience function for one-off calls from agent_runner.py (Phase 0.2)
    or a Celery task in tasks.py. Opens and closes its own HTTP client.
    """
    scrapper = GitHubScrapper(github_token=github_token)
    try:
        return scrapper.fetch_repo_stats(repo_url)
    finally:
        scrapper.close()
