"""Tests for the AtomWalker adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from opensift.adapters.atomwalker.adapter import AtomWalkerAdapter
from opensift.adapters.base.exceptions import ConfigurationError, ConnectionError, QueryError
from opensift.models.paper import PaperInfo
from opensift.models.query import SearchOptions

# ── Fixtures ──


@pytest.fixture
def sample_api_response() -> dict[str, Any]:
    """Sample API response mirroring real AtomWalker ScholarSearch output."""
    return {
        "papers": [
            {
                "url": "https://doi.org/10.1017/nlp.2024.53",
                "year": 2024,
                "title": "Maximizing RAG efficiency: A comparative analysis of RAG methods",
                "authors": "Tolga Şakar, Hakan Emekci",
                "authors_list": ["Tolga Şakar", "Hakan Emekci"],
                "abstract_text": (
                    "This paper addresses the optimization of retrieval-augmented generation (RAG) "
                    "processes by exploring various methodologies."
                ),
                "abstract_contents": None,
                "id": "1152921509010746362",
                "affiliations": "TED University; TED University",
                "conference_journal": "Natural language processing.",
                "conference_journal_type": "journal",
                "research_field": None,
                "doi": "10.1017/nlp.2024.53",
                "publication_date": "2024-10-30",
                "first_page": "1",
                "last_page": "25",
                "issn_l": "2977-0424",
                "issn": ["2977-0424"],
                "citation_count": 21,
                "source_url": "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/D7B259BCD35586E04358DF06006E0A85/paper.pdf",
                "jcr": {
                    "journal": "Natural Language Processing",
                    "issn": "N/A",
                    "eissn": "2977-0424",
                    "category": "COMPUTER SCIENCE, ARTIFICIAL INTELLIGENCE(SCIE);LANGUAGE & LINGUISTICS(AHCI);LINGUISTICS(SSCI)",
                    "if": "N/A",
                    "if_quartile": "N/A",
                    "if_rank": "N/A",
                },
                "ccf": None,
                "ccf_chinese": None,
                "fqb_jcr": {
                    "journal": "Natural Language Processing",
                    "year": "2025",
                    "issn": "2977-0424",
                    "eissn": "2977-0424",
                    "review": "否",
                    "oaj": "否",
                    "open_access": "否",
                    "web_of_science": "SCIE",
                    "label": "",
                    "major_category": "计算机科学",
                    "major_category_rank": "2 [103/758]",
                    "top": "否",
                    "sub_category_1": "COMPUTER SCIENCE, ARTIFICIAL INTELLIGENCE 计算机：人工智能",
                    "sub_category_1_rank": "2 [36/196]",
                    "sub_category_2": "LANGUAGE & LINGUISTICS 语言与语言学",
                    "sub_category_2_rank": "2 [34/391]",
                    "sub_category_3": "",
                    "sub_category_3_rank": "",
                    "sub_category_4": "",
                    "sub_category_4_rank": "",
                    "sub_category_5": "",
                    "sub_category_5_rank": "",
                    "sub_category_6": "",
                    "sub_category_6_rank": "",
                },
                "score": 1122.6566,
                "score_details": {
                    "grant_score": 0.0,
                    "base_score": 1.0,
                    "citation_score": 0.309,
                    "doi_score": 0.0,
                    "article_type_score": 0.1,
                    "non_review_score": 0.05,
                    "bm25_score": 658.53,
                    "open_access_score": 0.0,
                    "recency_score": 0.245,
                    "pdf_available_score": 0.0,
                    "journal_score": 0.0,
                },
            },
            {
                "url": "https://doi.org/10.1038/s41586-022-05652-7",
                "year": 2023,
                "title": "Structure of the lysosomal mTORC1–TFEB–Rag–Ragulator megacomplex",
                "authors": "Zhicheng Cui, Gennaro Napolitano, James H. Hurley",
                "authors_list": ["Zhicheng Cui", "Gennaro Napolitano", "James H. Hurley"],
                "abstract_text": ("The transcription factor TFEB is a master regulator of lysosomal biogenesis."),
                "abstract_contents": None,
                "id": "1152921508924799708",
                "affiliations": "QB3; University of California, Berkeley",
                "conference_journal": "Nature",
                "conference_journal_type": "journal",
                "research_field": None,
                "doi": "10.1038/s41586-022-05652-7",
                "publication_date": "2023-01-25",
                "citation_count": 158,
                "source_url": "https://www.nature.com/articles/s41586-022-05652-7.pdf",
                "jcr": {
                    "journal": "NATURE",
                    "issn": "0028-0836",
                    "eissn": "1476-4687",
                    "category": "MULTIDISCIPLINARY SCIENCES(SCIE)",
                    "if": "48.5",
                    "if_quartile": "Q1",
                    "if_rank": "2/135",
                },
                "ccf": None,
                "fqb_jcr": {
                    "journal": "NATURE",
                    "year": "2025",
                    "issn": "0028-0836",
                    "eissn": "1476-4687",
                    "review": "否",
                    "oaj": "否",
                    "open_access": "否",
                    "web_of_science": "SCIE",
                    "label": "",
                    "major_category": "综合性期刊",
                    "major_category_rank": "1 [1/118]",
                    "top": "是",
                    "sub_category_1": "MULTIDISCIPLINARY SCIENCES 综合性期刊",
                    "sub_category_1_rank": "1 [1/131]",
                    "sub_category_2": "",
                    "sub_category_2_rank": "",
                    "sub_category_3": "",
                    "sub_category_3_rank": "",
                    "sub_category_4": "",
                    "sub_category_4_rank": "",
                    "sub_category_5": "",
                    "sub_category_5_rank": "",
                    "sub_category_6": "",
                    "sub_category_6_rank": "",
                },
                "score": 1183.91,
            },
        ],
        "pagination": {"from": 0, "size": 10, "total": 10000, "has_more": True},
        "meta": {"query": "rag", "index": "atomwalker-works", "took_ms": 172},
    }


@pytest.fixture
def adapter() -> AtomWalkerAdapter:
    """Create an AtomWalker adapter instance (not initialised)."""
    return AtomWalkerAdapter(
        base_url="http://test-api.example.com",
        api_key="test-token-123",
        index="test-index",
        search_strategy="fast",
    )


# ── Tests: Adapter properties ──


class TestAtomWalkerAdapterProperties:
    """Tests for basic adapter properties."""

    def test_name(self, adapter: AtomWalkerAdapter) -> None:
        assert adapter.name == "atomwalker"

    def test_default_values(self) -> None:
        a = AtomWalkerAdapter()
        assert a._base_url == "http://wis-apihub-v2.dev.atominnolab.com"
        assert a._index == "atomwalker-works"
        assert a._search_strategy == "fast"
        assert a._timeout == 30.0

    def test_custom_values(self, adapter: AtomWalkerAdapter) -> None:
        assert adapter._base_url == "http://test-api.example.com"
        assert adapter._api_key == "test-token-123"
        assert adapter._index == "test-index"


# ── Tests: Initialization ──


class TestAtomWalkerInitialization:
    """Tests for adapter initialization."""

    @pytest.mark.asyncio
    async def test_initialize_without_api_key_raises(self) -> None:
        adapter = AtomWalkerAdapter(api_key="")
        with pytest.raises(ConfigurationError, match="API key is required"):
            await adapter.initialize()

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self, adapter: AtomWalkerAdapter) -> None:
        await adapter.initialize()
        assert adapter._client is not None
        assert isinstance(adapter._client, httpx.AsyncClient)
        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_closes_client(self, adapter: AtomWalkerAdapter) -> None:
        await adapter.initialize()
        await adapter.shutdown()
        assert adapter._client is None


# ── Tests: map_to_paper ──


class TestMapToPaper:
    """Tests for zero-loss PaperInfo mapping."""

    def test_map_full_paper(self, adapter: AtomWalkerAdapter, sample_api_response: dict) -> None:
        raw_paper = sample_api_response["papers"][0]
        paper = adapter.map_to_paper(raw_paper)

        assert isinstance(paper, PaperInfo)
        assert paper.title == "Maximizing RAG efficiency: A comparative analysis of RAG methods"
        assert paper.authors == "Tolga Şakar, Hakan Emekci"
        assert paper.affiliations == "TED University; TED University"
        assert paper.conference_journal == "Natural language processing."
        assert paper.publication_date == "2024-10-30"
        assert paper.citation_count == 21
        assert paper.doi == "https://doi.org/10.1017/nlp.2024.53"
        assert paper.abstract.startswith("This paper addresses")
        assert paper.source_url.endswith("paper.pdf")

    def test_map_paper_uses_jcr_category(self, adapter: AtomWalkerAdapter, sample_api_response: dict) -> None:
        """JCR category should override raw conference_journal_type."""
        raw_paper = sample_api_response["papers"][0]
        paper = adapter.map_to_paper(raw_paper)

        assert "COMPUTER SCIENCE" in paper.conference_journal_type
        assert "SCIE" in paper.conference_journal_type

    def test_map_paper_research_field_from_fqb_jcr(self, adapter: AtomWalkerAdapter, sample_api_response: dict) -> None:
        """When research_field is null, fall back to fqb_jcr categories."""
        raw_paper = sample_api_response["papers"][0]
        paper = adapter.map_to_paper(raw_paper)

        # Should have picked up major_category + sub_categories from fqb_jcr
        assert "计算机科学" in paper.research_field
        assert "COMPUTER SCIENCE" in paper.research_field

    def test_map_paper_doi_formatted_as_url(self, adapter: AtomWalkerAdapter) -> None:
        """DOIs without https:// prefix should get it added."""
        raw = {"doi": "10.1234/test.2024", "title": "Test"}
        paper = adapter.map_to_paper(raw)
        assert paper.doi == "https://doi.org/10.1234/test.2024"

    def test_map_paper_doi_already_url(self, adapter: AtomWalkerAdapter) -> None:
        """DOIs already formatted as URLs should not be changed."""
        raw = {"doi": "https://doi.org/10.1234/already", "title": "Test"}
        paper = adapter.map_to_paper(raw)
        assert paper.doi == "https://doi.org/10.1234/already"

    def test_map_paper_missing_fields_default_to_na(self, adapter: AtomWalkerAdapter) -> None:
        """Missing fields should default to 'N/A'."""
        raw: dict[str, Any] = {"id": "123"}
        paper = adapter.map_to_paper(raw)
        assert paper.title == "N/A"
        assert paper.authors == "N/A"
        assert paper.affiliations == "N/A"
        assert paper.doi == "N/A"
        assert paper.citation_count == 0

    def test_map_paper_fallback_abstract_contents(self, adapter: AtomWalkerAdapter) -> None:
        """Should fallback to abstract_contents if abstract_text is None."""
        raw = {"abstract_text": None, "abstract_contents": "Fallback content"}
        paper = adapter.map_to_paper(raw)
        assert paper.abstract == "Fallback content"

    def test_map_paper_source_url_fallback_to_url(self, adapter: AtomWalkerAdapter) -> None:
        """Should fallback to 'url' field if source_url is absent."""
        raw = {"source_url": None, "url": "https://example.com/paper"}
        paper = adapter.map_to_paper(raw)
        assert paper.source_url == "https://example.com/paper"


# ── Tests: map_to_standard_schema ──


class TestMapToStandardSchema:
    """Tests for StandardDocument mapping (backward compatibility)."""

    def test_maps_to_standard_document(self, adapter: AtomWalkerAdapter, sample_api_response: dict) -> None:
        raw = sample_api_response["papers"][0]
        doc = adapter.map_to_standard_schema(raw)

        assert doc.id == "1152921509010746362"
        assert doc.title == "Maximizing RAG efficiency: A comparative analysis of RAG methods"
        assert doc.content.startswith("This paper addresses")
        assert doc.score == 1122.6566
        assert doc.metadata.source == "Natural language processing."
        assert doc.metadata.author == "Tolga Şakar, Hakan Emekci"

    def test_extra_metadata_preserved(self, adapter: AtomWalkerAdapter, sample_api_response: dict) -> None:
        raw = sample_api_response["papers"][0]
        doc = adapter.map_to_standard_schema(raw)

        assert doc.metadata.extra["doi"] == "10.1017/nlp.2024.53"
        assert doc.metadata.extra["citation_count"] == 21
        assert doc.metadata.extra["jcr"] is not None
        assert doc.metadata.extra["fqb_jcr"] is not None


# ── Tests: search ──


class TestAtomWalkerSearch:
    """Tests for the search() method."""

    @pytest.mark.asyncio
    async def test_search_not_initialized_raises(self, adapter: AtomWalkerAdapter) -> None:
        with pytest.raises(ConnectionError, match="not initialized"):
            await adapter.search("rag", SearchOptions())

    @pytest.mark.asyncio
    async def test_search_returns_raw_results(self, adapter: AtomWalkerAdapter, sample_api_response: dict) -> None:
        await adapter.initialize()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = MagicMock()

        adapter._client.get = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        raw = await adapter.search("rag", SearchOptions(max_results=10))

        assert raw.total_hits == 10000
        assert len(raw.documents) == 2
        assert raw.metadata["has_more"] is True
        assert raw.metadata["query"] == "rag"

        # Verify the API was called with correct parameters
        adapter._client.get.assert_called_once()  # type: ignore[union-attr]
        call_args = adapter._client.get.call_args  # type: ignore[union-attr]
        assert "search" in call_args.kwargs["params"]
        assert call_args.kwargs["params"]["search"] == "rag"

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_search_http_error_raises_query_error(self, adapter: AtomWalkerAdapter) -> None:
        await adapter.initialize()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        adapter._client.get = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        with pytest.raises(QueryError, match="API error"):
            await adapter.search("test", SearchOptions())

        await adapter.shutdown()


# ── Tests: search_papers ──


class TestSearchPapers:
    """Tests for the direct search_papers() method."""

    @pytest.mark.asyncio
    async def test_search_papers_returns_paper_info_list(
        self, adapter: AtomWalkerAdapter, sample_api_response: dict
    ) -> None:
        await adapter.initialize()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = MagicMock()

        adapter._client.get = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        papers = await adapter.search_papers("rag", SearchOptions(max_results=10))

        assert len(papers) == 2
        assert all(isinstance(p, PaperInfo) for p in papers)
        assert papers[0].title == "Maximizing RAG efficiency: A comparative analysis of RAG methods"
        assert papers[1].title == "Structure of the lysosomal mTORC1–TFEB–Rag–Ragulator megacomplex"

        # Verify rich metadata is preserved
        assert papers[0].citation_count == 21
        assert papers[1].citation_count == 158

        await adapter.shutdown()


# ── Tests: health_check ──


class TestHealthCheck:
    """Tests for the health_check() method."""

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, adapter: AtomWalkerAdapter) -> None:
        health = await adapter.health_check()
        assert health.status == "unhealthy"
        assert "not initialized" in (health.message or "")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, adapter: AtomWalkerAdapter) -> None:
        await adapter.initialize()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"papers": [], "pagination": {}, "meta": {}}

        adapter._client.get = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        health = await adapter.health_check()
        assert health.status == "healthy"
        assert health.latency_ms >= 0

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, adapter: AtomWalkerAdapter) -> None:
        await adapter.initialize()

        mock_response = MagicMock()
        mock_response.status_code = 503

        adapter._client.get = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        health = await adapter.health_check()
        assert health.status == "degraded"

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_exception(self, adapter: AtomWalkerAdapter) -> None:
        await adapter.initialize()

        adapter._client.get = AsyncMock(  # type: ignore[union-attr]
            side_effect=httpx.ConnectError("Connection refused")
        )

        health = await adapter.health_check()
        assert health.status == "unhealthy"

        await adapter.shutdown()
