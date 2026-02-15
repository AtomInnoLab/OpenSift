"""Tests for the MeiliSearch adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from opensift.adapters.meilisearch.adapter import MeiliSearchAdapter
from opensift.models.query import SearchOptions

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def adapter() -> MeiliSearchAdapter:
    return MeiliSearchAdapter(
        base_url="http://localhost:7700",
        index="test_docs",
        api_key="test-key",
    )


@pytest.fixture
def sample_meili_hit() -> dict[str, Any]:
    """Sample MeiliSearch hit."""
    return {
        "id": "meili_001",
        "title": "Wind Power Forecasting",
        "content": "A deep learning approach to wind power output forecasting.",
        "author": "Alice Zhang",
        "url": "https://example.com/wind",
        "published_date": "2024-05-20",
        "tags": ["wind", "forecasting"],
        "_rankingScore": 0.92,
        "_formatted": {
            "title": "<em>Wind Power</em> Forecasting",
            "content": "A <em>deep learning</em> approach to <em>wind power</em> output forecasting.",
        },
    }


@pytest.fixture
def sample_meili_response(sample_meili_hit: dict) -> dict[str, Any]:
    """Sample MeiliSearch search response."""
    return {
        "hits": [sample_meili_hit],
        "estimatedTotalHits": 1,
        "offset": 0,
        "limit": 10,
        "processingTimeMs": 2,
        "query": "wind power forecasting",
    }


# ── Properties ───────────────────────────────────────────────────────────────


class TestMeiliSearchProperties:
    def test_name(self, adapter: MeiliSearchAdapter) -> None:
        assert adapter.name == "meilisearch"

    def test_default_values(self) -> None:
        a = MeiliSearchAdapter()
        assert a._base_url == "http://localhost:7700"
        assert a._index == "documents"

    def test_custom_values(self, adapter: MeiliSearchAdapter) -> None:
        assert adapter._index == "test_docs"
        assert adapter._api_key == "test-key"


# ── Schema Mapping ───────────────────────────────────────────────────────────


class TestMeiliSearchSchemaMapping:
    def test_map_to_standard_schema(self, adapter: MeiliSearchAdapter, sample_meili_hit: dict) -> None:
        doc = adapter.map_to_standard_schema(sample_meili_hit)
        assert doc.id == "meili_001"
        assert doc.title == "Wind Power Forecasting"
        assert "deep learning approach" in doc.content
        assert doc.snippet is not None  # From _formatted
        assert doc.score == 0.92
        assert doc.metadata.source == "test_docs"
        assert doc.metadata.url == "https://example.com/wind"
        assert doc.metadata.author == "Alice Zhang"
        assert "wind" in doc.metadata.tags
        assert doc.metadata.extra.get("meili_index") == "test_docs"

    def test_map_minimal_hit(self, adapter: MeiliSearchAdapter) -> None:
        doc = adapter.map_to_standard_schema({"id": "m1"})
        assert doc.id == "m1"
        assert doc.title == "Untitled"
        assert doc.score == 0.0

    def test_map_published_date_parsed(self, adapter: MeiliSearchAdapter, sample_meili_hit: dict) -> None:
        doc = adapter.map_to_standard_schema(sample_meili_hit)
        assert doc.metadata.published_date is not None
        assert doc.metadata.published_date.year == 2024


# ── Search ───────────────────────────────────────────────────────────────────


class TestMeiliSearchSearch:
    async def test_search_not_initialized_raises(self, adapter: MeiliSearchAdapter) -> None:
        from opensift.adapters.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError, match="not initialized"):
            await adapter.search("test", SearchOptions())

    async def test_search_returns_results(
        self, adapter: MeiliSearchAdapter, sample_meili_response: dict
    ) -> None:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_meili_response
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        adapter._client = mock_client

        results = await adapter.search("wind power forecasting", SearchOptions(max_results=10))
        assert results.total_hits == 1
        assert len(results.documents) == 1
        assert results.documents[0]["id"] == "meili_001"

    async def test_search_http_error(self, adapter: MeiliSearchAdapter) -> None:
        from opensift.adapters.base.exceptions import QueryError

        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=httpx.Request("POST", "http://test"),
            response=httpx.Response(400),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        adapter._client = mock_client

        with pytest.raises(QueryError, match="MeiliSearch query failed"):
            await adapter.search("test", SearchOptions())


# ── Fetch Document ───────────────────────────────────────────────────────────


class TestMeiliSearchFetchDocument:
    async def test_fetch_not_found(self, adapter: MeiliSearchAdapter) -> None:
        from opensift.adapters.base.exceptions import DocumentNotFoundError

        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response
        adapter._client = mock_client

        with pytest.raises(DocumentNotFoundError):
            await adapter.fetch_document("nonexistent")

    async def test_fetch_returns_doc(self, adapter: MeiliSearchAdapter) -> None:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "m1", "title": "Test"}
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response
        adapter._client = mock_client

        doc = await adapter.fetch_document("m1")
        assert doc["id"] == "m1"


# ── Health ───────────────────────────────────────────────────────────────────


class TestMeiliSearchHealth:
    async def test_health_not_initialized(self, adapter: MeiliSearchAdapter) -> None:
        health = await adapter.health_check()
        assert health.status == "unhealthy"

    async def test_health_available(self, adapter: MeiliSearchAdapter) -> None:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "available"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response
        adapter._client = mock_client

        health = await adapter.health_check()
        assert health.status == "healthy"
        assert "test_docs" in (health.message or "")

    async def test_health_exception(self, adapter: MeiliSearchAdapter) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = RuntimeError("Connection refused")
        adapter._client = mock_client

        health = await adapter.health_check()
        assert health.status == "unhealthy"


# ── Helpers ──────────────────────────────────────────────────────────────────


class TestMeiliSearchHelpers:
    def test_parse_recency_1y(self) -> None:
        result = MeiliSearchAdapter._parse_recency_filter("1y")
        assert result is not None
        assert "timestamp >" in result

    def test_parse_recency_30d(self) -> None:
        result = MeiliSearchAdapter._parse_recency_filter("30d")
        assert result is not None

    def test_parse_recency_invalid(self) -> None:
        assert MeiliSearchAdapter._parse_recency_filter("x") is None
        assert MeiliSearchAdapter._parse_recency_filter("") is None
