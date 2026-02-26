"""Integration tests for ElasticsearchAdapter against a real Elasticsearch instance."""

from __future__ import annotations

import pytest

from opensift.adapters.elasticsearch.adapter import ElasticsearchAdapter
from opensift.models.query import SearchOptions

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.elasticsearch]


@pytest.fixture
async def adapter(elasticsearch_ready):
    a = ElasticsearchAdapter(
        hosts=[elasticsearch_ready],
        index_pattern="test-docs",
    )
    await a.initialize()
    yield a
    await a.shutdown()


class TestElasticsearchHealth:
    async def test_health_check_returns_healthy(self, adapter):
        health = await adapter.health_check()
        assert health.status in ("healthy", "degraded")
        assert health.latency_ms >= 0

    async def test_name_property(self, adapter):
        assert adapter.name == "elasticsearch"


class TestElasticsearchSearch:
    async def test_search_returns_results(self, adapter):
        results = await adapter.search("solar nowcasting", SearchOptions(max_results=10))
        assert results.total_hits > 0
        assert len(results.documents) > 0

    async def test_search_relevance_solar(self, adapter):
        results = await adapter.search("solar irradiance deep learning", SearchOptions(max_results=10))
        titles = [d["_source"]["title"] for d in results.documents]
        assert any("Solar" in t for t in titles)

    async def test_search_relevance_transformer(self, adapter):
        results = await adapter.search("transformer NLP language model", SearchOptions(max_results=10))
        titles = [d["_source"]["title"] for d in results.documents]
        assert any("Transformer" in t for t in titles)

    async def test_search_no_results_for_gibberish(self, adapter):
        results = await adapter.search("xyzzyspoon999", SearchOptions(max_results=10))
        assert results.total_hits == 0

    async def test_search_max_results_limit(self, adapter):
        results = await adapter.search("learning", SearchOptions(max_results=2))
        assert len(results.documents) <= 2

    async def test_search_metadata_has_timing(self, adapter):
        results = await adapter.search("neural", SearchOptions(max_results=5))
        assert results.took_ms >= 0


class TestElasticsearchFetchDocument:
    async def test_fetch_existing_document(self, adapter):
        doc = await adapter.fetch_document("doc-001")
        assert doc["_source"]["title"] == "Advances in Solar Nowcasting Using Deep Learning"

    async def test_fetch_nonexistent_document_raises(self, adapter):
        from opensift.adapters.base.exceptions import DocumentNotFoundError

        with pytest.raises(DocumentNotFoundError):
            await adapter.fetch_document("nonexistent-999")


class TestElasticsearchSchemaMapping:
    async def test_map_to_standard_schema(self, adapter):
        results = await adapter.search("solar", SearchOptions(max_results=1))
        assert len(results.documents) > 0
        doc = adapter.map_to_standard_schema(results.documents[0])
        assert doc.title
        assert doc.content
        assert doc.id
        assert doc.metadata.source == "test-docs"

    async def test_search_and_normalize(self, adapter):
        docs = await adapter.search_and_normalize("drug discovery", SearchOptions(max_results=5))
        assert len(docs) > 0
        assert all(d.title for d in docs)
