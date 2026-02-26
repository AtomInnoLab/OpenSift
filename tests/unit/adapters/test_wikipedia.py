"""Tests for the Wikipedia adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from opensift.adapters.wikipedia.adapter import WikipediaAdapter
from opensift.models.query import SearchOptions

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def adapter() -> WikipediaAdapter:
    return WikipediaAdapter(language="en", max_chars=2000)


@pytest.fixture
def sample_wiki_doc() -> dict[str, Any]:
    """Sample Wikipedia article dict (as returned by _search_sync)."""
    return {
        "id": "wiki_en_12345",
        "title": "Solar power forecasting",
        "summary": (
            "Solar power forecasting is the process of predicting "
            "the output of solar energy systems using weather data."
        ),
        "search_snippet": '<span class="searchmatch">Solar</span> power forecasting is...',
        "full_url": "https://en.wikipedia.org/wiki/Solar_power_forecasting",
        "canonical_url": "https://en.wikipedia.org/wiki/Solar_power_forecasting",
        "url": "https://en.wikipedia.org/wiki/Solar_power_forecasting",
        "language": "en",
        "categories": ["Solar energy", "Weather forecasting"],
        "langlinks_count": 15,
        "word_count": 3500,
        "last_edited": "2025-01-15T12:00:00Z",
        "relevance_score": 1.0,
    }


def _make_mock_page(
    exists: bool = True,
    title: str = "Solar power forecasting",
    summary: str = "Solar power forecasting is the process of predicting output.",
    fullurl: str = "https://en.wikipedia.org/wiki/Solar_power_forecasting",
    canonicalurl: str = "https://en.wikipedia.org/wiki/Solar_power_forecasting",
    categories: dict | None = None,
    langlinks: dict | None = None,
    pageid: int = 12345,
) -> MagicMock:
    """Create a mock WikipediaPage."""
    page = MagicMock()
    page.exists.return_value = exists
    page.title = title
    page.summary = summary
    page.fullurl = fullurl
    page.canonicalurl = canonicalurl
    page.categories = categories or {"Category:Solar energy": MagicMock()}
    page.langlinks = langlinks or {"de": MagicMock(), "fr": MagicMock()}
    page.pageid = pageid
    return page


# ── Properties ───────────────────────────────────────────────────────────────


class TestWikipediaProperties:
    def test_name(self, adapter: WikipediaAdapter) -> None:
        assert adapter.name == "wikipedia"

    def test_default_values(self) -> None:
        a = WikipediaAdapter()
        assert a._language == "en"
        assert a._max_chars == 2000

    def test_custom_values(self) -> None:
        a = WikipediaAdapter(language="zh", max_chars=500)
        assert a._language == "zh"
        assert a._max_chars == 500


# ── Initialize ───────────────────────────────────────────────────────────────


class TestWikipediaInitialize:
    def test_initialize_missing_package(self, adapter: WikipediaAdapter) -> None:
        from opensift.adapters.base.exceptions import ConfigurationError

        with (
            patch.dict("sys.modules", {"wikipediaapi": None}),
            pytest.raises((ConfigurationError, ModuleNotFoundError)),
        ):
            import asyncio

            asyncio.get_event_loop().run_until_complete(adapter.initialize())

    def test_wiki_is_none_before_init(self, adapter: WikipediaAdapter) -> None:
        assert adapter._wiki is None


# ── Schema Mapping ───────────────────────────────────────────────────────────


class TestWikipediaSchemaMapping:
    def test_map_to_standard_schema(self, adapter: WikipediaAdapter, sample_wiki_doc: dict) -> None:
        doc = adapter.map_to_standard_schema(sample_wiki_doc)
        assert doc.id == "wiki_en_12345"
        assert doc.title == "Solar power forecasting"
        assert "predicting" in doc.content
        assert doc.snippet is not None
        assert "Solar" in doc.snippet
        assert doc.score == 1.0
        assert doc.metadata.source == "wikipedia_en"
        assert doc.metadata.url == "https://en.wikipedia.org/wiki/Solar_power_forecasting"
        assert doc.metadata.language == "en"
        assert doc.metadata.published_date is not None
        assert "Solar energy" in doc.metadata.tags
        assert doc.metadata.extra.get("langlinks_count") == 15
        assert doc.metadata.extra.get("word_count") == 3500

    def test_map_uses_relevance_score(self, adapter: WikipediaAdapter) -> None:
        doc = adapter.map_to_standard_schema(
            {
                "id": "w1",
                "title": "Test",
                "summary": "Test summary",
                "relevance_score": 0.75,
            }
        )
        assert doc.score == 0.75

    def test_map_minimal_doc(self, adapter: WikipediaAdapter) -> None:
        doc = adapter.map_to_standard_schema({"id": "w1"})
        assert doc.id == "w1"
        assert doc.title == "Untitled"
        assert doc.score == 1.0
        assert doc.metadata.source == "wikipedia_en"

    def test_map_with_chinese_language(self) -> None:
        adapter = WikipediaAdapter(language="zh")
        doc = adapter.map_to_standard_schema(
            {
                "id": "wiki_zh_1",
                "title": "太阳能预报",
                "summary": "太阳能预报是预测太阳能输出的过程。",
                "language": "zh",
            }
        )
        assert doc.metadata.source == "wikipedia_zh"
        assert doc.metadata.language == "zh"


# ── Search ───────────────────────────────────────────────────────────────────


def _make_fulltext_search_response(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a mock MediaWiki action=query&list=search API response."""
    return {
        "batchcomplete": "",
        "query": {
            "searchinfo": {"totalhits": len(results)},
            "search": results,
        },
    }


def _mock_urlopen_for(response_dict: dict[str, Any]) -> MagicMock:
    """Create a mock urlopen context-manager that returns *response_dict* as JSON."""
    import json
    from io import BytesIO

    response_bytes = json.dumps(response_dict).encode("utf-8")
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=BytesIO(response_bytes))
    mock.__exit__ = MagicMock(return_value=False)
    return mock


class TestWikipediaSearch:
    async def test_search_not_initialized_raises(self, adapter: WikipediaAdapter) -> None:
        from opensift.adapters.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError, match="not initialized"):
            await adapter.search("test", SearchOptions())

    def test_search_sync_returns_documents(self, adapter: WikipediaAdapter) -> None:
        """Test the synchronous _search_sync helper with mocked wikipedia-api."""
        mock_wiki = MagicMock()
        mock_page = _make_mock_page()
        mock_wiki.page.return_value = mock_page
        adapter._wiki = mock_wiki

        import urllib.request

        api_response = _make_fulltext_search_response(
            [
                {
                    "ns": 0,
                    "title": "Solar power forecasting",
                    "pageid": 12345,
                    "size": 28000,
                    "wordcount": 3500,
                    "snippet": '<span class="searchmatch">Solar</span> power forecasting...',
                    "timestamp": "2025-01-15T12:00:00Z",
                },
            ]
        )

        with patch.object(urllib.request, "urlopen", return_value=_mock_urlopen_for(api_response)):
            docs = adapter._search_sync("solar", max_results=5)

        assert len(docs) == 1
        assert docs[0]["title"] == "Solar power forecasting"
        assert "wikipedia.org" in docs[0]["url"]
        assert docs[0]["relevance_score"] == 1.0
        assert docs[0]["word_count"] == 3500

    def test_search_sync_relevance_ranking(self, adapter: WikipediaAdapter) -> None:
        """Multiple results should have descending relevance scores."""
        mock_wiki = MagicMock()
        mock_page = _make_mock_page()
        mock_wiki.page.return_value = mock_page
        adapter._wiki = mock_wiki

        import urllib.request

        api_response = _make_fulltext_search_response(
            [
                {
                    "ns": 0,
                    "title": "Page A",
                    "pageid": 1,
                    "size": 1000,
                    "wordcount": 100,
                    "snippet": "A",
                    "timestamp": "2025-01-01T00:00:00Z",
                },
                {
                    "ns": 0,
                    "title": "Page B",
                    "pageid": 2,
                    "size": 2000,
                    "wordcount": 200,
                    "snippet": "B",
                    "timestamp": "2025-01-02T00:00:00Z",
                },
                {
                    "ns": 0,
                    "title": "Page C",
                    "pageid": 3,
                    "size": 3000,
                    "wordcount": 300,
                    "snippet": "C",
                    "timestamp": "2025-01-03T00:00:00Z",
                },
            ]
        )

        with patch.object(urllib.request, "urlopen", return_value=_mock_urlopen_for(api_response)):
            docs = adapter._search_sync("test", max_results=5)

        assert len(docs) == 3
        scores = [d["relevance_score"] for d in docs]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] > scores[-1]

    def test_search_sync_nonexistent_page(self, adapter: WikipediaAdapter) -> None:
        """Pages that don't exist should be skipped."""
        mock_wiki = MagicMock()
        mock_page = _make_mock_page(exists=False)
        mock_wiki.page.return_value = mock_page
        adapter._wiki = mock_wiki

        import urllib.request

        api_response = _make_fulltext_search_response(
            [
                {
                    "ns": 0,
                    "title": "NonexistentPage",
                    "pageid": 99999,
                    "size": 0,
                    "wordcount": 0,
                    "snippet": "",
                    "timestamp": "",
                },
            ]
        )

        with patch.object(urllib.request, "urlopen", return_value=_mock_urlopen_for(api_response)):
            docs = adapter._search_sync("nonexistent", max_results=5)

        assert len(docs) == 0

    def test_search_sync_truncates_summary(self, adapter: WikipediaAdapter) -> None:
        """Long summaries should be truncated."""
        adapter._max_chars = 50
        mock_wiki = MagicMock()
        long_summary = "A" * 200
        mock_page = _make_mock_page(summary=long_summary)
        mock_wiki.page.return_value = mock_page
        adapter._wiki = mock_wiki

        import urllib.request

        api_response = _make_fulltext_search_response(
            [
                {
                    "ns": 0,
                    "title": "Page",
                    "pageid": 1,
                    "size": 5000,
                    "wordcount": 500,
                    "snippet": "Desc",
                    "timestamp": "2025-01-01T00:00:00Z",
                },
            ]
        )

        with patch.object(urllib.request, "urlopen", return_value=_mock_urlopen_for(api_response)):
            docs = adapter._search_sync("q", max_results=5)

        assert len(docs) == 1
        assert len(docs[0]["summary"]) <= 51 + 1  # 50 chars + "…"

    def test_search_sync_empty_results(self, adapter: WikipediaAdapter) -> None:
        """Empty search results should return an empty list."""
        adapter._wiki = MagicMock()

        import urllib.request

        api_response = _make_fulltext_search_response([])

        with patch.object(urllib.request, "urlopen", return_value=_mock_urlopen_for(api_response)):
            docs = adapter._search_sync("xyznonexistent", max_results=5)

        assert docs == []


# ── Fetch Document ───────────────────────────────────────────────────────────


class TestWikipediaFetchDocument:
    async def test_fetch_not_initialized(self, adapter: WikipediaAdapter) -> None:
        from opensift.adapters.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError, match="not initialized"):
            await adapter.fetch_document("Test Page")

    def test_fetch_nonexistent_page(self, adapter: WikipediaAdapter) -> None:
        from opensift.adapters.base.exceptions import DocumentNotFoundError

        mock_wiki = MagicMock()
        mock_page = _make_mock_page(exists=False)
        mock_wiki.page.return_value = mock_page
        adapter._wiki = mock_wiki

        import asyncio

        with pytest.raises(DocumentNotFoundError, match="not found"):
            asyncio.get_event_loop().run_until_complete(adapter.fetch_document("NonexistentPage"))


# ── Health ───────────────────────────────────────────────────────────────────


class TestWikipediaHealth:
    async def test_health_not_initialized(self, adapter: WikipediaAdapter) -> None:
        health = await adapter.health_check()
        assert health.status == "unhealthy"
        assert "not initialized" in (health.message or "")

    def test_health_check_success(self, adapter: WikipediaAdapter) -> None:
        """Synchronous test for health check with mocked page."""
        mock_wiki = MagicMock()
        mock_page = _make_mock_page(title="Python_(programming_language)")
        mock_wiki.page.return_value = mock_page
        adapter._wiki = mock_wiki

        import asyncio

        health = asyncio.get_event_loop().run_until_complete(adapter.health_check())
        assert health.status == "healthy"
        assert "en" in (health.message or "")

    def test_health_check_page_not_found(self, adapter: WikipediaAdapter) -> None:
        mock_wiki = MagicMock()
        mock_page = _make_mock_page(exists=False)
        mock_wiki.page.return_value = mock_page
        adapter._wiki = mock_wiki

        import asyncio

        health = asyncio.get_event_loop().run_until_complete(adapter.health_check())
        assert health.status == "degraded"
