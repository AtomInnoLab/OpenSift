"""Integration tests for WikipediaAdapter against the live Wikipedia API.

No Docker container needed — tests hit the public Wikipedia API directly.
These tests use well-known topics to ensure stable results.
"""

from __future__ import annotations

import pytest

from opensift.adapters.wikipedia.adapter import WikipediaAdapter
from opensift.models.query import SearchOptions

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.wikipedia]


@pytest.fixture
async def adapter():
    a = WikipediaAdapter(language="en")
    await a.initialize()
    yield a
    await a.shutdown()


class TestWikipediaHealth:
    async def test_health_check_returns_healthy(self, adapter):
        health = await adapter.health_check()
        assert health.status == "healthy"
        assert health.latency_ms >= 0

    async def test_name_property(self, adapter):
        assert adapter.name == "wikipedia"


class TestWikipediaSearch:
    async def test_search_returns_results(self, adapter):
        results = await adapter.search("Albert Einstein", SearchOptions(max_results=5))
        assert results.total_hits > 0
        assert len(results.documents) > 0

    async def test_search_relevance(self, adapter):
        results = await adapter.search("Python programming language", SearchOptions(max_results=5))
        titles = [d.get("title", "") for d in results.documents]
        assert any("Python" in t for t in titles)

    async def test_search_no_results_for_gibberish(self, adapter):
        results = await adapter.search("xyzzy999qqq888zzz", SearchOptions(max_results=5))
        assert results.total_hits == 0

    async def test_search_max_results_limit(self, adapter):
        results = await adapter.search("machine learning", SearchOptions(max_results=3))
        assert len(results.documents) <= 3


class TestWikipediaSchemaMapping:
    async def test_map_to_standard_schema(self, adapter):
        results = await adapter.search("solar energy", SearchOptions(max_results=1))
        assert len(results.documents) > 0
        doc = adapter.map_to_standard_schema(results.documents[0])
        assert doc.title
        assert doc.content
        assert doc.metadata.url

    async def test_search_and_normalize(self, adapter):
        docs = await adapter.search_and_normalize("deep learning", SearchOptions(max_results=3))
        assert len(docs) > 0
        assert all(d.title for d in docs)
        assert all(d.metadata.url for d in docs)
