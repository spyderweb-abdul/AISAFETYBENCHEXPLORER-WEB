"""Deterministic paper-fetching tool for Phase 3 extraction.

The backing LLM (OpenAI/Anthropic chat completion) has no built-in ability to
fetch external URLs -- it can only reason from its training data. This module
performs the actual Phase 0.1 "Fetch the Paper" step from the master prompt
using real HTTP calls, then hands the fetched text to the model as context.

Supported source_type values: "doi", "arxiv_id", "pdf_url".
"""
from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
CROSSREF_API_URL = "https://api.crossref.org/works/{doi}"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}"

_HTTP_TIMEOUT = 20.0


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


def fetch_semantic_scholar_citation_count(title_or_doi: str, api_key: str = "") -> int | None:
    """Best-effort citation count lookup by title or DOI search.

    Passing api_key raises Semantic Scholar's unauthenticated rate limit
    (1 request/second, frequent 429s) to the much higher authenticated tier.
    Get a free key at https://www.semanticscholar.org/product/api.

    If the key is rejected (403 -- "the API key you've sent is incorrect",
    per Semantic Scholar's own FAQ), automatically retries once without any
    key, falling back to the public unauthenticated tier rather than failing
    the whole lookup. This keeps extraction working end-to-end even with a
    misconfigured/not-yet-activated key.
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
        resp = _do_request(use_key=bool(api_key))
        if resp.status_code == 403 and api_key:
            logger.warning(
                "Semantic Scholar rejected API key (403) for %s; "
                "retrying unauthenticated.", title_or_doi,
            )
            resp = _do_request(use_key=False)
        resp.raise_for_status()
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

    Same 403-retry-without-key fallback as fetch_semantic_scholar_citation_count.
    """
    try:
        paper_id = identifier
        if identifier.lower().startswith(("10.", "https://doi.org/", "doi:")):
            clean = _extract_clean_doi(identifier)
            paper_id = f"DOI:{clean}"

        def _do_request(use_key: bool) -> httpx.Response:
            headers = {"x-api-key": api_key} if (use_key and api_key) else {}
            return httpx.get(
                SEMANTIC_SCHOLAR_URL.format(paper_id=paper_id),
                params={"fields": "title,abstract,authors,year,citationCount,externalIds,openAccessPdf"},
                timeout=_HTTP_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            )

        resp = _do_request(use_key=bool(api_key))
        if resp.status_code == 403 and api_key:
            logger.warning(
                "Semantic Scholar rejected API key (403) for %s; "
                "retrying unauthenticated.", identifier,
            )
            resp = _do_request(use_key=False)

        if resp.status_code == 404:
            return {"source": "semantic_scholar", "fetch_ok": False, "error": "404 not found"}
        resp.raise_for_status()
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

    if result.get("fetch_ok") and result.get("citation_count") is None:
        title_or_doi = result.get("title") or result.get("doi") or source_value
        citation_count = fetch_semantic_scholar_citation_count(
            title_or_doi, api_key=semantic_scholar_api_key
        )
        if citation_count is not None:
            result["citation_count"] = citation_count

    return result
