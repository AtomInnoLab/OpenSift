"""Tests for the OpenSearch adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opensift.adapters.opensearch.adapter import OpenSearchAdapter
from opensift.models.query import SearchOptions

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def adapter() -> OpenSearchAdapter:
    return OpenSearchAdapter(
        hosts=["https://localhost:9200"],
        index_pattern="test-*",
    )


@pytest.fixture
def sample_hit() -> dict[str, Any]:
    """Sample OpenSearch hit document."""
    return {
        "_index": "test-docs",
        "_id": "doc_001",
        "_score": 8.5,
        "_source": {
            "title": "Solar Nowcasting with Deep Learning",
            "content": "We propose a novel approach to solar irradiance nowcasting.",
            "author": "Jane Doe",
            "url": "https://example.com/paper1",
            "published_date": "2024-06-15T00:00:00Z",
            "tags": ["solar", "deep-learning"],
        },
        "highlight": {
            "content": ["<em>solar irradiance</em> nowcasting"],
        },
    }


# ── Properties ───────────────────────────────────────────────────────────────


class TestOpenSearchAdapterProperties:
    def test_name(self, adapter: OpenSearchAdapter) -> None:
        assert adapter.name == "opensearch"

    def test_default_hosts(self) -> None:
        a = OpenSearchAdapter()
        assert a._hosts == ["https://localhost:9200"]

    def test_custom_hosts(self, adapter: OpenSearchAdapter) -> None:
        assert adapter._hosts == ["https://localhost:9200"]
        assert adapter._index_pattern == "test-*"


# ── Initialization ───────────────────────────────────────────────────────────


class TestOpenSearchInitialization:
    async def test_initialize_missing_package_raises(self) -> None:
        from opensift.adapters.base.exceptions import ConfigurationError

        adapter = OpenSearchAdapter()
        with patch.dict("sys.modules", {"opensearchpy": None}), pytest.raises((ConfigurationError, ModuleNotFoundError)):
            await adapter.initialize()

    async def test_shutdown_closes_client(self) -> None:
        adapter = OpenSearchAdapter()
        mock_client = AsyncMock()
        adapter._client = mock_client
        await adapter.shutdown()
        mock_client.close.assert_called_once()
        assert adapter._client is None


# ── Schema Mapping ───────────────────────────────────────────────────────────


class TestOpenSearchSchemaMapping:
    def test_map_to_standard_schema(self, adapter: OpenSearchAdapter, sample_hit: dict) -> None:
        doc = adapter.map_to_standard_schema(sample_hit)
        assert doc.id == "doc_001"
        assert doc.title == "Solar Nowcasting with Deep Learning"
        assert "solar irradiance nowcasting" in doc.content
        assert doc.snippet is not None
        assert doc.score == 8.5
        assert doc.metadata.source == "test-docs"
        assert doc.metadata.url == "https://example.com/paper1"
        assert doc.metadata.author == "Jane Doe"
        assert "solar" in doc.metadata.tags
        assert doc.metadata.extra.get("os_index") == "test-docs"

    def test_map_minimal_hit(self, adapter: OpenSearchAdapter) -> None:
        doc = adapter.map_to_standard_schema({"_id": "x", "_source": {}})
        assert doc.id == "x"
        assert doc.title == "Untitled"

    def test_map_published_date_parsed(self, adapter: OpenSearchAdapter, sample_hit: dict) -> None:
        doc = adapter.map_to_standard_schema(sample_hit)
        assert doc.metadata.published_date is not None
        assert doc.metadata.published_date.year == 2024


# ── Search ───────────────────────────────────────────────────────────────────


class TestOpenSearchSearch:
    async def test_search_not_initialized_raises(self, adapter: OpenSearchAdapter) -> None:
        from opensift.adapters.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError, match="not initialized"):
            await adapter.search("test", SearchOptions())

    async def test_search_returns_results(self, adapter: OpenSearchAdapter, sample_hit: dict) -> None:
        mock_client = AsyncMock()
        mock_client.search.return_value = {
            "took": 5,
            "hits": {
                "total": {"value": 1},
                "hits": [sample_hit],
            },
        }
        adapter._client = mock_client

        results = await adapter.search("solar nowcasting", SearchOptions(max_results=10))
        assert results.total_hits == 1
        assert len(results.documents) == 1
        assert results.documents[0]["_id"] == "doc_001"


# ── Health ───────────────────────────────────────────────────────────────────


class TestOpenSearchHealth:
    async def test_health_not_initialized(self, adapter: OpenSearchAdapter) -> None:
        health = await adapter.health_check()
        assert health.status == "unhealthy"

    async def test_health_healthy(self, adapter: OpenSearchAdapter) -> None:
        mock_client = MagicMock()
        mock_client.cluster = MagicMock()
        mock_client.cluster.health = AsyncMock(
            return_value={"status": "green", "cluster_name": "test-cluster", "number_of_nodes": 3}
        )
        adapter._client = mock_client

        health = await adapter.health_check()
        assert health.status == "healthy"
        assert "test-cluster" in (health.message or "")

    async def test_health_exception(self, adapter: OpenSearchAdapter) -> None:
        mock_client = MagicMock()
        mock_client.cluster = MagicMock()
        mock_client.cluster.health = AsyncMock(side_effect=RuntimeError("Connection refused"))
        adapter._client = mock_client

        health = await adapter.health_check()
        assert health.status == "unhealthy"


# ── Helpers ──────────────────────────────────────────────────────────────────


class TestOpenSearchHelpers:
    def test_parse_recency_1y(self) -> None:
        result = OpenSearchAdapter._parse_recency_filter("1y")
        assert result is not None
        assert "now-1y/year" in str(result)

    def test_parse_recency_30d(self) -> None:
        result = OpenSearchAdapter._parse_recency_filter("30d")
        assert result is not None

    def test_parse_recency_invalid(self) -> None:
        assert OpenSearchAdapter._parse_recency_filter("x") is None
        assert OpenSearchAdapter._parse_recency_filter("") is None
