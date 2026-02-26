"""Integration tests for MeiliSearchAdapter against a real MeiliSearch instance."""

from __future__ import annotations

import pytest

from opensift.adapters.meilisearch.adapter import MeiliSearchAdapter
from opensift.models.query import SearchOptions

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.meilisearch]


@pytest.fixture
async def adapter(meilisearch_ready):
    a = MeiliSearchAdapter(
        base_url=meilisearch_ready,
        index="test-docs",
        api_key="test-master-key",
    )
    await a.initialize()
    yield a
    await a.shutdown()


class TestMeiliSearchHealth:
    async def test_health_check_returns_healthy(self, adapter):
        health = await adapter.health_check()
        assert health.status == "healthy"
        assert health.latency_ms >= 0

    async def test_name_property(self, adapter):
        assert adapter.name == "meilisearch"


class TestMeiliSearchSearch:
    async def test_search_returns_results(self, adapter):
        results = await adapter.search("solar nowcasting", SearchOptions(max_results=10))
        assert results.total_hits > 0
        assert len(results.documents) > 0

    async def test_search_relevance_solar(self, adapter):
        results = await adapter.search("solar deep learning", SearchOptions(max_results=10))
        titles = [d.get("title", "") for d in results.documents]
        assert any("Solar" in t for t in titles)

    async def test_search_relevance_graph(self, adapter):
        results = await adapter.search("graph neural network drug", SearchOptions(max_results=10))
        titles = [d.get("title", "") for d in results.documents]
        assert any("Graph" in t for t in titles)

    async def test_search_typo_tolerance(self, adapter):
        """MeiliSearch should handle typos gracefully."""
        results = await adapter.search("transformr languge model", SearchOptions(max_results=10))
        assert results.total_hits > 0

    async def test_search_no_results_for_gibberish(self, adapter):
        results = await adapter.search("xyzzyspoon999qqq", SearchOptions(max_results=10))
        assert results.total_hits == 0

    async def test_search_max_results_limit(self, adapter):
        results = await adapter.search("learning", SearchOptions(max_results=2))
        assert len(results.documents) <= 2

    async def test_search_metadata_has_timing(self, adapter):
        results = await adapter.search("neural", SearchOptions(max_results=5))
        assert results.took_ms >= 0


class TestMeiliSearchFetchDocument:
    async def test_fetch_existing_document(self, adapter):
        doc = await adapter.fetch_document("doc-004")
        assert doc["title"] == "Reinforcement Learning for Robotic Manipulation"

    async def test_fetch_nonexistent_document_raises(self, adapter):
        from opensift.adapters.base.exceptions import DocumentNotFoundError

        with pytest.raises(DocumentNotFoundError):
            await adapter.fetch_document("nonexistent-999")


class TestMeiliSearchSchemaMapping:
    async def test_map_to_standard_schema(self, adapter):
        results = await adapter.search("solar", SearchOptions(max_results=1))
        assert len(results.documents) > 0
        doc = adapter.map_to_standard_schema(results.documents[0])
        assert doc.title
        assert doc.content
        assert doc.id
        assert doc.metadata.source == "test-docs"

    async def test_search_and_normalize(self, adapter):
        docs = await adapter.search_and_normalize("privacy", SearchOptions(max_results=5))
        assert len(docs) > 0
        assert all(d.title for d in docs)
