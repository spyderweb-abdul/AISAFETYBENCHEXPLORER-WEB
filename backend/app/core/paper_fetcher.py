"""Deterministic paper-fetching tool.

The backing LLM (OpenAI/Anthropic chat completion) has no built-in ability to
fetch external URLs -- it can only reason from its training data. This module
performs the actual Phase 0.1 "Fetch the Paper" step from the master prompt
using real HTTP calls, then hands the fetched text to the model as context.

Supported source_type values: "doi", "arxiv_id", "pdf_url".
"""
from __future__ import annotations

import logging
import random
import re
import time
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
CROSSREF_API_URL = "https://api.crossref.org/works/{doi}"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}"

_HTTP_TIMEOUT = 20.0


class SemanticScholarKeyRejectedError(RuntimeError):
    """The configured API key was rejected; do not retry anonymously."""


def _clean_arxiv_id(value: str) -> str:
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", value)
    return match.group(1) if match else value.strip()


def fetch_arxiv(arxiv_id: str) -> dict[str, str]:
    """Fetch title, authors, and abstract from the arXiv API (not the PDF body)."""
    clean_id = _clean_arxiv_id(arxiv_id)
    try:
        resp = httpx.get(
            ARXIV_API_URL,
            params={"id_list": clean_id},
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        xml = resp.text

        title_match = re.search(r"<title>(.*?)</title>", xml, re.DOTALL)
        summary_match = re.search(r"<summary>(.*?)</summary>", xml, re.DOTALL)
        authors = re.findall(r"<name>(.*?)</name>", xml)
        published_match = re.search(r"<published>(.*?)</published>", xml)

        titles = re.findall(r"<title>(.*?)</title>", xml, re.DOTALL)
        title = titles[1].strip() if len(titles) > 1 else (title_match.group(1).strip() if title_match else "")

        return {
            "source": "arxiv",
            "arxiv_id": clean_id,
            "title": title,
            "abstract": summary_match.group(1).strip() if summary_match else "",
            "authors": ", ".join(authors),
            "published": published_match.group(1).strip() if published_match else "",
            "url": f"https://arxiv.org/abs/{clean_id}",
            "fetch_ok": bool(title and summary_match),
        }
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("arXiv fetch failed for %s: %s", arxiv_id, exc)
        return {"source": "arxiv", "arxiv_id": clean_id, "fetch_ok": False, "error": str(exc)}


DATACITE_API_URL = "https://api.datacite.org/dois/{doi}"

_ARXIV_DOI_RE = re.compile(r"10\.48550/arxiv\.(.+)", re.IGNORECASE)


def _extract_clean_doi(doi: str) -> str:
    clean_doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if clean_doi.lower().startswith(prefix):
            clean_doi = clean_doi[len(prefix):]
            break
    return clean_doi


def fetch_doi(doi: str) -> dict[str, str]:
    """Fetch title, authors, and abstract for a DOI.

    IMPORTANT: arXiv-minted DOIs (prefix 10.48550/arXiv.*) are registered with
    DataCite, NOT Crossref -- Crossref will always 404 on these regardless of
    whether the paper is real. See https://info.arxiv.org/help/doi.html.
    We detect this case and redirect straight to the arXiv API (fetch_arxiv),
    which is authoritative for arXiv papers anyway. For all other (non-arXiv)
    DOIs we try Crossref first, then fall back to DataCite if Crossref 404s,
    since DataCite also covers many non-Crossref-registered DOIs (e.g. Zenodo).
    """
    clean_doi = _extract_clean_doi(doi)

    arxiv_match = _ARXIV_DOI_RE.match(clean_doi)
    if arxiv_match:
        logger.info("DOI %s is an arXiv-minted DOI; delegating to fetch_arxiv.", clean_doi)
        result = fetch_arxiv(arxiv_match.group(1))
        result["doi"] = clean_doi
        return result

    crossref_result = _fetch_doi_crossref(clean_doi)
    if crossref_result.get("fetch_ok"):
        return crossref_result

    logger.info("Crossref failed for %s (%s); trying DataCite fallback.", clean_doi, crossref_result.get("error"))
    datacite_result = _fetch_doi_datacite(clean_doi)
    if datacite_result.get("fetch_ok"):
        return datacite_result

    return crossref_result


def _fetch_doi_crossref(clean_doi: str) -> dict[str, str]:
    try:
        resp = httpx.get(
            CROSSREF_API_URL.format(doi=clean_doi),
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": "AISafetyBenchExplorer/0.3 (mailto:admin@example.com)"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        message = resp.json().get("message", {})

        title = (message.get("title") or [""])[0]
        authors = ", ".join(
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in message.get("author", [])
        )
        abstract = re.sub(r"<[^>]+>", "", message.get("abstract", "") or "")
        published_parts = (
            message.get("published-print", {}).get("date-parts")
            or message.get("published-online", {}).get("date-parts")
            or [[]]
        )[0]
        published = "-".join(str(p) for p in published_parts) if published_parts else ""

        return {
            "source": "crossref",
            "doi": clean_doi,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published": published,
            "venue": (message.get("container-title") or [""])[0],
            "crossref_citation_count": message.get("is-referenced-by-count"),
            "url": f"https://doi.org/{clean_doi}",
            "fetch_ok": bool(title),
        }
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("Crossref fetch failed for %s: %s", clean_doi, exc)
        return {"source": "crossref", "doi": clean_doi, "fetch_ok": False, "error": str(exc)}


def _fetch_doi_datacite(clean_doi: str) -> dict[str, str]:
    try:
        resp = httpx.get(DATACITE_API_URL.format(doi=clean_doi), timeout=_HTTP_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        attrs = resp.json().get("data", {}).get("attributes", {})

        titles = attrs.get("titles") or [{}]
        title = titles[0].get("title", "") if titles else ""
        creators = attrs.get("creators") or []
        authors = ", ".join(c.get("name", "") for c in creators if c.get("name"))
        descriptions = attrs.get("descriptions") or []
        abstract = next(
            (d.get("description", "") for d in descriptions if d.get("descriptionType") == "Abstract"),
            "",
        )
        published = str(attrs.get("published") or attrs.get("publicationYear") or "")

        return {
            "source": "datacite",
            "doi": clean_doi,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published": published,
            "venue": attrs.get("publisher") or "",
            "url": f"https://doi.org/{clean_doi}",
            "fetch_ok": bool(title),
        }
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("DataCite fetch failed for %s: %s", clean_doi, exc)
        return {"source": "datacite", "doi": clean_doi, "fetch_ok": False, "error": str(exc)}


def fetch_pdf_url(pdf_url: str) -> dict[str, str]:
    """Download a PDF and extract its text with pypdf. Truncates to keep the
    LLM context manageable; full-document extraction is a Phase 4+ concern."""
    try:
        import io

        from pypdf import PdfReader

        resp = httpx.get(pdf_url, timeout=_HTTP_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()

        reader = PdfReader(io.BytesIO(resp.content))
        pages_text = []
        for page in reader.pages[:15]:
            pages_text.append(page.extract_text() or "")
        full_text = "\n".join(pages_text)[:20000]

        return {
            "source": "pdf",
            "url": pdf_url,
            "title": "",
            "abstract": full_text[:2000],
            "full_text_excerpt": full_text,
            "fetch_ok": bool(full_text.strip()),
        }
    except Exception as exc:
        logger.warning("PDF fetch/parse failed for %s: %s", pdf_url, exc)
        return {"source": "pdf", "url": pdf_url, "fetch_ok": False, "error": str(exc)}


def _semantic_scholar_backoff_sleep(attempt: int) -> None:
    """Exponential backoff with jitter for Semantic Scholar 429 retries."""
    base = min(2 ** attempt, 8)
    jitter = random.uniform(0.0, 0.5)
    time.sleep(base + jitter)


def _semantic_scholar_request_with_retry(do_request, log_label: str, api_key: str = "") -> httpx.Response:
    """Runs a Semantic Scholar request with:
    - 403 with a configured key -> fail fast without an anonymous retry.
    - 429 (rate limited) -> exponential backoff retry, up to 3 attempts total.
    Raises the last exception/HTTP error if all attempts are exhausted.

    A rejected configured key is an authentication/configuration problem, not
    a reason to fall back to the shared anonymous quota. In bulk refreshes,
    that fallback turns one bad key into repeated 429s and unnecessary delay.
    """
    last_exc = None
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            resp = do_request(use_key=bool(api_key))

            if resp.status_code == 403 and api_key:
                logger.warning(
                    "Semantic Scholar rejected configured API key (403) for %s; "
                    "skipping anonymous fallback.",
                    log_label,
                )
                raise SemanticScholarKeyRejectedError(
                    "Semantic Scholar rejected the configured API key."
                )

            if resp.status_code == 429:
                logger.warning(
                    "Semantic Scholar rate limited request for %s (429), attempt %s/%s.",
                    log_label, attempt + 1, max_attempts,
                )
                if attempt < max_attempts - 1:
                    _semantic_scholar_backoff_sleep(attempt)
                    continue

            resp.raise_for_status()
            return resp

        except SemanticScholarKeyRejectedError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                _semantic_scholar_backoff_sleep(attempt)
                continue
            break

    raise last_exc


def fetch_semantic_scholar_citation_count(title_or_doi: str, api_key: str = "") -> int | None:
    """Best-effort citation count lookup by title or DOI search.

    Passing api_key raises Semantic Scholar's unauthenticated rate limit
    (1 request/second, frequent 429s) to the much higher authenticated tier.
    Get a free key at https://www.semanticscholar.org/product/api.

    A rejected configured key fails fast so callers can use a different
    source rather than exhausting the shared anonymous quota. 429 responses
    retry with exponential backoff (up to 3 attempts total).
    """

    def _do_request(use_key: bool) -> httpx.Response:
        headers = {"x-api-key": api_key} if (use_key and api_key) else {}
        return httpx.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": title_or_doi, "fields": "citationCount,title", "limit": 1},
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        )

    try:
        resp = _semantic_scholar_request_with_retry(
            _do_request, log_label=title_or_doi, api_key=api_key,
        )
        data = resp.json().get("data", [])
        if data:
            return data[0].get("citationCount")
    except Exception as exc:
        logger.warning("Semantic Scholar lookup failed for %s: %s", title_or_doi, exc)
    return None


def fetch_semantic_scholar_paper(identifier: str, api_key: str = "") -> dict[str, str]:
    """Last-resort fallback: look up a DOI/arXiv ID/title directly on Semantic
    Scholar, which indexes far more sources than Crossref or DataCite alone
    (it aggregates arXiv, DOI-registered venues, and many preprint servers).

    A rejected configured key fails fast; 429 responses retry with exponential
    backoff.
    """
    try:
        paper_id = identifier
        if identifier.lower().startswith(("10.", "https://doi.org/", "doi:")):
            clean = _extract_clean_doi(identifier)
            paper_id = f"DOI:{clean}"

        def _do_request(use_key: bool) -> httpx.Response:
            headers = {"x-api-key": api_key} if (use_key and api_key) else {}
            return httpx.get(
                SEMANTIC_SCHOLAR_URL.format(paper_id=quote(paper_id, safe=":")),
                params={"fields": "title,abstract,authors,year,citationCount,externalIds,openAccessPdf"},
                timeout=_HTTP_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            )

        resp = _semantic_scholar_request_with_retry(
            _do_request, log_label=identifier, api_key=api_key,
        )

        if resp.status_code == 404:
            return {"source": "semantic_scholar", "fetch_ok": False, "error": "404 not found"}

        data = resp.json()
        authors = ", ".join(a.get("name", "") for a in data.get("authors", []) if a.get("name"))
        return {
            "source": "semantic_scholar",
            "title": data.get("title", ""),
            "abstract": data.get("abstract") or "",
            "authors": authors,
            "published": str(data.get("year", "")),
            "citation_count": data.get("citationCount"),
            "url": data.get("openAccessPdf", {}).get("url", ""),
            "fetch_ok": bool(data.get("title")),
        }
    except Exception as exc:
        logger.warning("Semantic Scholar direct lookup failed for %s: %s", identifier, exc)
        return {"source": "semantic_scholar", "fetch_ok": False, "error": str(exc)}


def fetch_source(source_type: str, source_value: str, semantic_scholar_api_key: str = "") -> dict[str, str]:
    """Dispatch to the correct fetcher based on source_type, with Semantic
    Scholar as a final fallback if the primary source-specific fetch fails.

    semantic_scholar_api_key, if provided, is forwarded to every Semantic
    Scholar call to avoid the strict unauthenticated rate limit (which
    otherwise causes frequent 429 errors under normal usage).
    """
    if source_type == "arxiv_id":
        result = fetch_arxiv(source_value)
    elif source_type == "doi":
        result = fetch_doi(source_value)
    elif source_type == "pdf_url":
        result = fetch_pdf_url(source_value)
    else:
        return {"fetch_ok": False, "error": f"Unknown source_type: {source_type}"}

    if not result.get("fetch_ok") and source_type in ("doi", "arxiv_id"):
        logger.info(
            "%s fetch failed for %s; trying Semantic Scholar as final fallback.",
            source_type, source_value,
        )
        ss_result = fetch_semantic_scholar_paper(source_value, api_key=semantic_scholar_api_key)
        if ss_result.get("fetch_ok"):
            result = ss_result

    return result


def resolve_paper_metadata(
    source_type: str | None,
    source_value: str | None,
    *,
    fetched: dict[str, Any] | None = None,
    semantic_scholar_api_key: str = "",
) -> dict[str, Any]:
    """Resolve source-backed paper metadata for persistence.

    Semantic Scholar is queried by a stable DOI or arXiv identifier whenever
    one is available. That direct lookup is deliberately preferred over the
    title-search helper used by older records: a title search can select a
    different paper with a similar name. Crossref's reference count remains a
    clearly-labelled fallback rather than being presented as a citation count.
    """
    base = fetched or {}
    source_text = source_value or ""
    if not base and source_type and source_value:
        base = fetch_source(source_type, source_value, semantic_scholar_api_key=semantic_scholar_api_key)

    doi = base.get("doi")
    arxiv_id = base.get("arxiv_id")
    if source_type == "doi" and source_text:
        doi = _extract_clean_doi(source_text)
    elif source_type == "arxiv_id" and source_text:
        arxiv_id = _clean_arxiv_id(source_text)

    if not doi and source_text:
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", source_text, re.IGNORECASE)
        if doi_match:
            doi = _extract_clean_doi(doi_match.group(0))
    if not arxiv_id and source_text:
        arxiv_match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", source_text)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)

    if doi and _ARXIV_DOI_RE.match(doi):
        arxiv_id = _ARXIV_DOI_RE.match(doi).group(1)

    # Citation refreshes for older records start from paper_link rather than
    # an extraction source type. Fetch Crossref/DataCite or arXiv first so
    # their bibliographic fields and cited-by value remain useful fallbacks.
    if not base and doi:
        base = fetch_doi(doi)
    elif not base and arxiv_id:
        base = fetch_arxiv(arxiv_id)

    result: dict[str, Any] = {
        "fetch_ok": bool(base.get("fetch_ok")),
        "doi": doi,
        "arxiv_id": arxiv_id,
        "canonical_title": base.get("title") or "",
        "authors": base.get("authors") or "",
        "venue": base.get("venue") or "",
        "publication_date": base.get("published") or "",
        "is_open_access": None,
        "open_access_url": base.get("url") or "",
        "metadata_source": base.get("source") or None,
        "citation_count": None,
        "citation_source": None,
        "error": base.get("error"),
    }

    paper_id = f"DOI:{doi}" if doi else (f"ARXIV:{arxiv_id}" if arxiv_id else None)
    if paper_id:
        try:
            def _do_request(use_key: bool) -> httpx.Response:
                headers = {"x-api-key": semantic_scholar_api_key} if (use_key and semantic_scholar_api_key) else {}
                return httpx.get(
                    SEMANTIC_SCHOLAR_URL.format(paper_id=quote(paper_id, safe=":")),
                    params={
                        "fields": (
                            "paperId,title,authors,venue,publicationVenue,publicationDate,year,"
                            "externalIds,isOpenAccess,openAccessPdf,citationCount"
                        )
                    },
                    timeout=_HTTP_TIMEOUT,
                    follow_redirects=True,
                    headers=headers,
                )

            data = _semantic_scholar_request_with_retry(
                _do_request, log_label=paper_id, api_key=semantic_scholar_api_key,
            ).json()
            external_ids = data.get("externalIds") or {}
            oa_pdf = data.get("openAccessPdf") or {}
            publication_venue = data.get("publicationVenue") or {}
            result.update(
                fetch_ok=bool(data.get("title")),
                doi=external_ids.get("DOI") or doi,
                arxiv_id=external_ids.get("ArXiv") or arxiv_id,
                semantic_scholar_paper_id=data.get("paperId"),
                canonical_title=data.get("title") or result["canonical_title"],
                authors=", ".join(a.get("name", "") for a in data.get("authors", []) if a.get("name")),
                venue=publication_venue.get("name") or data.get("venue") or result["venue"],
                publication_date=data.get("publicationDate") or data.get("year") or result["publication_date"],
                is_open_access=data.get("isOpenAccess"),
                open_access_url=oa_pdf.get("url") or result["open_access_url"],
                metadata_source="Semantic Scholar",
                citation_count=data.get("citationCount"),
                citation_source="Semantic Scholar",
                error=None,
            )
            return result
        except SemanticScholarKeyRejectedError:
            result["semantic_scholar_key_rejected"] = True
            result["error"] = "Semantic Scholar rejected the configured API key."
        except Exception as exc:
            logger.warning("Semantic Scholar metadata lookup failed for %s: %s", paper_id, exc)
            result["error"] = str(exc)

    if base.get("citation_count") is not None:
        result["citation_count"] = base["citation_count"]
        result["citation_source"] = "Semantic Scholar search"
    elif base.get("crossref_citation_count") is not None:
        result["citation_count"] = base["crossref_citation_count"]
        result["citation_source"] = "Crossref cited-by count"
    elif source_text and not result.get("semantic_scholar_key_rejected"):
        citation_count = fetch_semantic_scholar_citation_count(
            source_text, api_key=semantic_scholar_api_key,
        )
        if citation_count is not None:
            result["citation_count"] = citation_count
            result["citation_source"] = "Semantic Scholar search"
    if result["citation_count"] is not None:
        result["error"] = None
    return result
