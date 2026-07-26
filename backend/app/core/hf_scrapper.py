"""
hf_scrapper.py

Deterministic HuggingFace Hub dataset/model activity scraper for
AISafetyBenchExplorer-Web.

Companion to github_scrapper.py: together they close Known Gap 10 (Phase 3),
replacing the agent's own agentic web_search calls for HuggingFace metadata
with a real, auditable, rate-limit-aware HTTP tool.

Feeds repo_stats (FK to benchmarks) alongside github_scrapper.py's output.
HuggingFace dataset staleness and likes/downloads are secondary signals used
alongside GitHub stars in the complexity-methodology.md decision tree
(community reach, adoption breadth indicators for Popular/High tiers), and
directly support the catalogue's own reported finding of 96/195 stale
HuggingFace datasets.

Usage as a deterministic tool (called by agent_runner.py during Phase 0.2,
or by the Celery Beat scheduled refresh task in tasks.py):

    from app.core.hf_scrapper import fetch_hf_dataset_stats, fetch_hf_model_stats
    stats = fetch_hf_dataset_stats("owner/dataset-name")
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

HF_API_BASE = "https://huggingface.co/api"
HF_URL_PATTERN = re.compile(
    r"huggingface\.co/(?:datasets/)?(?P<owner>[\w.-]+)/(?P<name>[\w.-]+?)/?$"
)


@dataclass
class HFResourceStats:
    resource_type: str
    owner: str
    name: str
    likes: int
    downloads: Optional[int]
    last_modified_at: Optional[datetime]
    days_since_last_modified: Optional[int]
    is_private: bool
    is_gated: bool
    license_id: Optional[str]
    activity_status: str
    fetched_at: datetime
    error: Optional[str] = None


def parse_hf_identifier(value: str) -> Optional[tuple[str, str]]:
    """
    Accepts either a bare 'owner/name' identifier or a full
    huggingface.co URL (dataset or model) and returns (owner, name).
    """
    value = value.strip()
    match = HF_URL_PATTERN.search(value)
    if match:
        return match.group("owner"), match.group("name")

    bare_match = re.match(r"^(?P<owner>[\w.-]+)/(?P<name>[\w.-]+)$", value)
    if bare_match:
        return bare_match.group("owner"), bare_match.group("name")

    return None


def _is_retryable_http_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (429, 500, 502, 503, 504):
            return True
    return False


class HFScrapper:
    """
    Thin, deterministic wrapper around the HuggingFace Hub REST API.
    Mirrors GitHubScrapper's design in github_scrapper.py: every field
    returned here is reproducible and auditable, per Section 2 of
    PROJECT_ROADMAP.md's Agent-as-Orchestrator architecture.
    """

    def __init__(self, hf_token: Optional[str] = None, timeout: float = 10.0):
        headers = {}
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        self._client = httpx.Client(
            base_url=HF_API_BASE, headers=headers, timeout=timeout
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

    def _fetch(self, resource_type: str, identifier: str) -> HFResourceStats:
        parsed = parse_hf_identifier(identifier)
        now = datetime.now(timezone.utc)

        if parsed is None:
            logger.warning("hf_scrapper: unparseable %s identifier %r", resource_type, identifier)
            return HFResourceStats(
                resource_type=resource_type,
                owner="",
                name="",
                likes=0,
                downloads=None,
                last_modified_at=None,
                days_since_last_modified=None,
                is_private=False,
                is_gated=False,
                license_id=None,
                activity_status="unknown",
                fetched_at=now,
                error="unparseable_identifier",
            )

        owner, name = parsed
        endpoint = f"/datasets/{owner}/{name}" if resource_type == "dataset" else f"/models/{owner}/{name}"

        try:
            resp = self._get(endpoint)
        except httpx.HTTPError as exc:
            logger.error("hf_scrapper: %s fetch failed for %s/%s: %s", resource_type, owner, name, exc)
            return HFResourceStats(
                resource_type=resource_type,
                owner=owner,
                name=name,
                likes=0,
                downloads=None,
                last_modified_at=None,
                days_since_last_modified=None,
                is_private=False,
                is_gated=False,
                license_id=None,
                activity_status="unknown",
                fetched_at=now,
                error=f"fetch_failed: {exc}",
            )

        if resp.status_code == 404:
            return HFResourceStats(
                resource_type=resource_type,
                owner=owner,
                name=name,
                likes=0,
                downloads=None,
                last_modified_at=None,
                days_since_last_modified=None,
                is_private=False,
                is_gated=False,
                license_id=None,
                activity_status="not_found",
                fetched_at=now,
                error="resource_not_found",
            )

        data = resp.json()

        last_modified_at: Optional[datetime] = None
        raw_last_modified = data.get("lastModified")
        if raw_last_modified:
            try:
                last_modified_at = datetime.fromisoformat(raw_last_modified.replace("Z", "+00:00"))
            except ValueError:
                logger.warning("hf_scrapper: unparseable lastModified %r for %s/%s", raw_last_modified, owner, name)

        days_since_last_modified: Optional[int] = None
        if last_modified_at is not None:
            days_since_last_modified = (now - last_modified_at).days

        card_data = data.get("cardData") or {}
        license_id = card_data.get("license") or data.get("license")

        is_gated_raw = data.get("gated", False)
        is_gated = bool(is_gated_raw) if isinstance(is_gated_raw, bool) else is_gated_raw != "false"

        if days_since_last_modified is None:
            activity_status = "unknown"
        elif days_since_last_modified <= 90:
            activity_status = "active"
        elif days_since_last_modified <= 365:
            activity_status = "slowing"
        else:
            activity_status = "stale"

        return HFResourceStats(
            resource_type=resource_type,
            owner=owner,
            name=name,
            likes=data.get("likes", 0),
            downloads=data.get("downloads"),
            last_modified_at=last_modified_at,
            days_since_last_modified=days_since_last_modified,
            is_private=bool(data.get("private", False)),
            is_gated=is_gated,
            license_id=license_id,
            activity_status=activity_status,
            fetched_at=now,
            error=None,
        )

    def fetch_dataset_stats(self, identifier: str) -> HFResourceStats:
        return self._fetch("dataset", identifier)

    def fetch_model_stats(self, identifier: str) -> HFResourceStats:
        return self._fetch("model", identifier)


def fetch_hf_dataset_stats(identifier: str, hf_token: Optional[str] = None) -> HFResourceStats:
    """
    Convenience function for one-off calls from agent_runner.py (Phase 0.2)
    or a Celery task in tasks.py. Opens and closes its own HTTP client.
    """
    scrapper = HFScrapper(hf_token=hf_token)
    try:
        return scrapper.fetch_dataset_stats(identifier)
    finally:
        scrapper.close()


def fetch_hf_model_stats(identifier: str, hf_token: Optional[str] = None) -> HFResourceStats:
    scrapper = HFScrapper(hf_token=hf_token)
    try:
        return scrapper.fetch_model_stats(identifier)
    finally:
        scrapper.close()
