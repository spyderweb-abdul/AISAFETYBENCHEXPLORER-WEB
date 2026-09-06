import pytest

from app.core import paper_fetcher


class _Response:
    def json(self):
        return {
            "paperId": "semantic-id",
            "title": "Verified paper title",
            "authors": [{"name": "Ada Lovelace"}],
            "publicationVenue": {"name": "Research Journal"},
            "publicationDate": "2025-02-03",
            "externalIds": {"DOI": "10.1234/example"},
            "isOpenAccess": True,
            "openAccessPdf": {"url": "https://example.test/paper.pdf"},
            "citationCount": 42,
        }


def test_metadata_resolver_prefers_direct_semantic_scholar_identifier(monkeypatch):
    requested = []

    def fake_request(do_request, log_label, api_key=""):
        requested.append(log_label)
        return _Response()

    monkeypatch.setattr(paper_fetcher, "_semantic_scholar_request_with_retry", fake_request)

    resolved = paper_fetcher.resolve_paper_metadata(
        "doi",
        "https://doi.org/10.1234/example",
        fetched={"fetch_ok": True, "source": "crossref", "title": "Unverified title"},
    )

    assert requested == ["DOI:10.1234/example"]
    assert resolved["citation_count"] == 42
    assert resolved["citation_source"] == "Semantic Scholar"
    assert resolved["canonical_title"] == "Verified paper title"
    assert resolved["metadata_source"] == "Semantic Scholar"


def test_rejected_key_does_not_retry_against_anonymous_quota():
    calls = []

    class ForbiddenResponse:
        status_code = 403

    def request(use_key):
        calls.append(use_key)
        return ForbiddenResponse()

    with pytest.raises(paper_fetcher.SemanticScholarKeyRejectedError):
        paper_fetcher._semantic_scholar_request_with_retry(
            request, log_label="DOI:10.1234/example", api_key="configured-key",
        )

    assert calls == [True]
