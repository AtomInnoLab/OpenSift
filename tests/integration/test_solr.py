"""Integration tests for SolrAdapter against a real Solr instance."""

from __future__ import annotations

import pytest

from opensift.adapters.solr.adapter import SolrAdapter
from opensift.models.query import SearchOptions

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.solr]


@pytest.fixture
async def adapter(solr_ready):
    a = SolrAdapter(
        base_url=solr_ready,
        collection="documents",
    )
    await a.initialize()
    yield a
    await a.shutdown()


class TestSolrHealth:
    async def test_health_check_returns_healthy(self, adapter):
        health = await adapter.health_check()
        assert health.status == "healthy"
        assert health.latency_ms >= 0

    async def test_name_property(self, adapter):
        assert adapter.name == "solr"


class TestSolrSearch:
    async def test_search_returns_results(self, adapter):
        results = await adapter.search("solar nowcasting", SearchOptions(max_results=10))
        assert results.total_hits > 0
        assert len(results.documents) > 0

    async def test_search_relevance_solar(self, adapter):
        results = await adapter.search("solar irradiance deep learning", SearchOptions(max_results=10))
        titles = [d.get("title", "") for d in results.documents]
        # Solr may return title as list
        flat = [t[0] if isinstance(t, list) else t for t in titles]
        assert any("Solar" in t for t in flat)

    async def test_search_relevance_robotics(self, adapter):
        results = await adapter.search("reinforcement learning robotics", SearchOptions(max_results=10))
        titles = [d.get("title", "") for d in results.documents]
        flat = [t[0] if isinstance(t, list) else t for t in titles]
        assert any("Robotic" in t for t in flat)

    async def test_search_no_results_for_gibberish(self, adapter):
        results = await adapter.search("xyzzyspoon999", SearchOptions(max_results=10))
        assert results.total_hits == 0

    async def test_search_max_results_limit(self, adapter):
        results = await adapter.search("learning", SearchOptions(max_results=2))
        assert len(results.documents) <= 2

    async def test_search_metadata_has_timing(self, adapter):
        results = await adapter.search("neural", SearchOptions(max_results=5))
        assert results.took_ms >= 0


class TestSolrFetchDocument:
    async def test_fetch_existing_document(self, adapter):
        doc = await adapter.fetch_document("doc-003")
        title = doc.get("title", "")
        if isinstance(title, list):
            title = title[0]
        assert "Federated" in title

    async def test_fetch_nonexistent_document_raises(self, adapter):
        from opensift.adapters.base.exceptions import DocumentNotFoundError

        with pytest.raises(DocumentNotFoundError):
            await adapter.fetch_document("nonexistent-999")


class TestSolrSchemaMapping:
    async def test_map_to_standard_schema(self, adapter):
        results = await adapter.search("drug discovery", SearchOptions(max_results=1))
        assert len(results.documents) > 0
        doc = adapter.map_to_standard_schema(results.documents[0])
        assert doc.title
        assert doc.content
        assert doc.id

    async def test_search_and_normalize(self, adapter):
        docs = await adapter.search_and_normalize("federated", SearchOptions(max_results=5))
        assert len(docs) > 0
        assert all(d.title for d in docs)
