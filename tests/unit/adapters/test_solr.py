"""Tests for the Apache Solr adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from opensift.adapters.solr.adapter import SolrAdapter
from opensift.models.query import SearchOptions

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def adapter() -> SolrAdapter:
    return SolrAdapter(
        base_url="http://localhost:8983/solr",
        collection="test_docs",
    )


@pytest.fixture
def sample_solr_doc() -> dict[str, Any]:
    """Sample Solr document from a /select response."""
    return {
        "id": "doc_solar_001",
        "title": "Solar Energy Forecasting Methods",
        "content": "A comprehensive survey of solar energy forecasting approaches.",
        "author": "John Smith",
        "url": "https://example.com/solar-survey",
        "published_date": "2024-03-10T00:00:00Z",
        "tags": ["solar", "forecasting", "survey"],
        "score": 12.3,
        "_highlighting": {
            "content": ["<em>solar energy</em> forecasting approaches"],
        },
    }


@pytest.fixture
def sample_solr_response(sample_solr_doc: dict) -> dict[str, Any]:
    """Sample Solr JSON response from /select."""
    return {
        "responseHeader": {"status": 0, "QTime": 3},
        "response": {
            "numFound": 1,
            "start": 0,
            "docs": [sample_solr_doc],
        },
        "highlighting": {
            "doc_solar_001": {
                "content": ["<em>solar energy</em> forecasting approaches"],
            },
        },
    }


# ── Properties ───────────────────────────────────────────────────────────────


class TestSolrProperties:
    def test_name(self, adapter: SolrAdapter) -> None:
        assert adapter.name == "solr"

    def test_default_values(self) -> None:
        a = SolrAdapter()
        assert a._base_url == "http://localhost:8983/solr"
        assert a._collection == "documents"

    def test_custom_values(self, adapter: SolrAdapter) -> None:
        assert adapter._collection == "test_docs"


# ── Schema Mapping ───────────────────────────────────────────────────────────


class TestSolrSchemaMapping:
    def test_map_to_standard_schema(self, adapter: SolrAdapter, sample_solr_doc: dict) -> None:
        doc = adapter.map_to_standard_schema(sample_solr_doc)
        assert doc.id == "doc_solar_001"
        assert doc.title == "Solar Energy Forecasting Methods"
        assert "comprehensive survey" in doc.content
        assert doc.snippet is not None
        assert doc.score == 12.3
        assert doc.metadata.source == "test_docs"
        assert doc.metadata.url == "https://example.com/solar-survey"
        assert doc.metadata.author == "John Smith"
        assert "solar" in doc.metadata.tags
        assert doc.metadata.extra.get("solr_collection") == "test_docs"

    def test_map_minimal_doc(self, adapter: SolrAdapter) -> None:
        doc = adapter.map_to_standard_schema({"id": "x"})
        assert doc.id == "x"
        assert doc.title == "Untitled"

    def test_map_list_valued_title(self, adapter: SolrAdapter) -> None:
        """Solr may return single fields as lists."""
        doc = adapter.map_to_standard_schema({"id": "x", "title": ["Multi-valued Title"]})
        assert doc.title == "Multi-valued Title"

    def test_map_published_date_parsed(self, adapter: SolrAdapter, sample_solr_doc: dict) -> None:
        doc = adapter.map_to_standard_schema(sample_solr_doc)
        assert doc.metadata.published_date is not None
        assert doc.metadata.published_date.year == 2024


# ── Search ───────────────────────────────────────────────────────────────────


class TestSolrSearch:
    async def test_search_not_initialized_raises(self, adapter: SolrAdapter) -> None:
        from opensift.adapters.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError, match="not initialized"):
            await adapter.search("test", SearchOptions())

    async def test_search_returns_results(self, adapter: SolrAdapter, sample_solr_response: dict) -> None:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_solr_response
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        adapter._client = mock_client

        results = await adapter.search("solar forecasting", SearchOptions(max_results=10))
        assert results.total_hits == 1
        assert len(results.documents) == 1
        assert results.documents[0]["id"] == "doc_solar_001"
        # Highlighting should be attached to the doc
        assert "_highlighting" in results.documents[0]

    async def test_search_http_error(self, adapter: SolrAdapter) -> None:
        from opensift.adapters.base.exceptions import QueryError

        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=httpx.Request("POST", "http://test"),
            response=httpx.Response(500),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        adapter._client = mock_client

        with pytest.raises(QueryError, match="Solr query failed"):
            await adapter.search("test", SearchOptions())


# ── Fetch Document ───────────────────────────────────────────────────────────


class TestSolrFetchDocument:
    async def test_fetch_not_found(self, adapter: SolrAdapter) -> None:
        from opensift.adapters.base.exceptions import DocumentNotFoundError

        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"doc": None}
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response
        adapter._client = mock_client

        with pytest.raises(DocumentNotFoundError):
            await adapter.fetch_document("nonexistent")

    async def test_fetch_returns_doc(self, adapter: SolrAdapter) -> None:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"doc": {"id": "d1", "title": "Test"}}
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response
        adapter._client = mock_client

        doc = await adapter.fetch_document("d1")
        assert doc["id"] == "d1"


# ── Health ───────────────────────────────────────────────────────────────────


class TestSolrHealth:
    async def test_health_not_initialized(self, adapter: SolrAdapter) -> None:
        health = await adapter.health_check()
        assert health.status == "unhealthy"

    async def test_health_ok(self, adapter: SolrAdapter) -> None:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response
        adapter._client = mock_client

        health = await adapter.health_check()
        assert health.status == "healthy"
        assert "test_docs" in (health.message or "")

    async def test_health_exception(self, adapter: SolrAdapter) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = RuntimeError("Connection refused")
        adapter._client = mock_client

        health = await adapter.health_check()
        assert health.status == "unhealthy"


# ── Helpers ──────────────────────────────────────────────────────────────────


class TestSolrHelpers:
    def test_first_value_list(self) -> None:
        assert SolrAdapter._first_value(["hello"]) == "hello"

    def test_first_value_scalar(self) -> None:
        assert SolrAdapter._first_value("hello") == "hello"

    def test_first_value_empty_list(self) -> None:
        assert SolrAdapter._first_value([]) == ""

    def test_parse_recency_1y(self) -> None:
        result = SolrAdapter._parse_recency_filter("1y")
        assert result is not None
        assert "NOW-" in result
        assert "YEAR" in result

    def test_parse_recency_30d(self) -> None:
        result = SolrAdapter._parse_recency_filter("30d")
        assert result is not None

    def test_parse_recency_invalid(self) -> None:
        assert SolrAdapter._parse_recency_filter("x") is None
        assert SolrAdapter._parse_recency_filter("") is None
