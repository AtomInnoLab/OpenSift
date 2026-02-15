"""AtomWalker adapter — Academic paper search via the ScholarSearch API.

Connects to the AtomWalker ScholarSearch service and returns academic papers
with full metadata (title, authors, affiliations, abstract, journal info,
JCR/CCF rankings, citation counts, etc.).

API reference:
  GET /api/v1/resource/ScholarSearch/paper/atomwalker-works
    ?search=<query>
    &search_strategy=<fast|comprehensive>
    &from=<offset>
    &size=<page_size>
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from opensift.adapters.base.adapter import AdapterHealth, RawResults, SearchAdapter
from opensift.adapters.base.exceptions import ConfigurationError, ConnectionError, QueryError
from opensift.models.document import DocumentMetadata, StandardDocument
from opensift.models.paper import PaperInfo
from opensift.models.query import SearchOptions

logger = logging.getLogger(__name__)


class AtomWalkerAdapter(SearchAdapter):
    """Search adapter for the AtomWalker ScholarSearch API.

    Provides academic paper search with rich metadata including:
      - Full bibliographic data (title, authors, affiliations, DOI)
      - Journal/conference info with JCR impact factor and quartile
      - CCF ranking (for CS venues)
      - FQB/JCR Chinese Academy of Sciences classification
      - BM25 relevance scores and citation counts

    Args:
        base_url: AtomWalker API base URL.
        api_key: Bearer token for authentication.
        index: Search index name (default: 'atomwalker-works').
        search_strategy: Search strategy ('fast' or 'comprehensive').
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = "http://wis-apihub-v2.dev.atominnolab.com",
        api_key: str = "",
        index: str = "atomwalker-works",
        search_strategy: str = "fast",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._index = index
        self._search_strategy = search_strategy
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "atomwalker"

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        if not self._api_key:
            raise ConfigurationError(
                "AtomWalker API key is required. "
                "Set it via adapter config: adapters.atomwalker.api_key"
            )

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
            },
            timeout=self._timeout,
        )
        logger.info("AtomWalker adapter initialized (index: %s)", self._index)

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(self, query: str, options: SearchOptions) -> RawResults:
        """Execute a search query against the AtomWalker API.

        Args:
            query: The search query string.
            options: Search behavior options.

        Returns:
            RawResults with paper dicts as documents.
        """
        if not self._client:
            raise ConnectionError("AtomWalker client not initialized.")

        params: dict[str, Any] = {
            "search": query,
            "search_strategy": self._search_strategy,
            "size": options.max_results,
        }

        endpoint = f"/api/v1/resource/ScholarSearch/paper/{self._index}"

        try:
            start = time.monotonic()
            response = await self._client.get(endpoint, params=params)
            response.raise_for_status()
            took_ms = int((time.monotonic() - start) * 1000)

            data = response.json()
            papers = data.get("papers", [])
            pagination = data.get("pagination", {})
            meta = data.get("meta", {})

            logger.debug(
                "AtomWalker search: query=%s, results=%d, took=%dms (api=%dms)",
                query,
                len(papers),
                took_ms,
                meta.get("took_ms", 0),
            )

            return RawResults(
                total_hits=pagination.get("total", len(papers)),
                documents=papers,
                metadata={
                    "query": meta.get("query", query),
                    "index": meta.get("index", self._index),
                    "api_took_ms": meta.get("took_ms", 0),
                    "has_more": pagination.get("has_more", False),
                },
                took_ms=took_ms,
            )
        except httpx.HTTPStatusError as e:
            raise QueryError(f"AtomWalker API error ({e.response.status_code}): {e.response.text[:200]}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"AtomWalker request failed: {e}") from e

    async def fetch_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve a single paper by ID.

        Note: AtomWalker does not currently expose a single-document endpoint.
        This searches for the paper by ID as a fallback.
        """
        if not self._client:
            raise ConnectionError("AtomWalker client not initialized.")

        # Fallback: search by ID
        options = SearchOptions(max_results=1)
        raw = await self.search(doc_id, options)
        if raw.documents:
            return raw.documents[0]
        raise QueryError(f"Paper not found: {doc_id}")

    def map_to_standard_schema(self, raw_result: dict[str, Any]) -> StandardDocument:
        """Map an AtomWalker paper to StandardDocument.

        This provides backward compatibility with the generic adapter interface.
        For full metadata, use `map_to_paper()` instead.
        """
        paper_id = str(raw_result.get("id", ""))
        title = raw_result.get("title", "Untitled")
        abstract = raw_result.get("abstract_text") or raw_result.get("abstract_contents") or ""
        authors = raw_result.get("authors", "")
        url = raw_result.get("url", "")
        doi = raw_result.get("doi", "")
        source_url = raw_result.get("source_url", "")
        conference_journal = raw_result.get("conference_journal", "")
        publication_date = raw_result.get("publication_date", "")
        citation_count = raw_result.get("citation_count", 0)
        score = raw_result.get("score", 0.0)

        # Parse date
        parsed_date = None
        if publication_date:
            import contextlib

            with contextlib.suppress(ValueError, TypeError):
                parsed_date = datetime.fromisoformat(publication_date)

        return StandardDocument(
            id=paper_id,
            title=title,
            content=abstract,
            snippet=abstract[:200] if abstract else None,
            score=score,
            metadata=DocumentMetadata(
                source=conference_journal or "atomwalker",
                url=url or source_url,
                published_date=parsed_date,
                author=authors,
                extra={
                    "doi": doi,
                    "citation_count": citation_count,
                    "affiliations": raw_result.get("affiliations", ""),
                    "conference_journal_type": raw_result.get("conference_journal_type", ""),
                    "research_field": raw_result.get("research_field"),
                    "jcr": raw_result.get("jcr"),
                    "ccf": raw_result.get("ccf"),
                    "fqb_jcr": raw_result.get("fqb_jcr"),
                    "score_details": raw_result.get("score_details"),
                },
            ),
        )

    def map_to_paper(self, raw_result: dict[str, Any]) -> PaperInfo:
        """Map an AtomWalker paper directly to PaperInfo (zero-loss).

        This preserves all academic metadata from the API response.

        Args:
            raw_result: Raw paper dict from the AtomWalker API.

        Returns:
            A fully populated PaperInfo.
        """
        # Determine conference_journal_type
        # Prefer JCR category if available, otherwise use raw type
        journal_type = raw_result.get("conference_journal_type", "N/A") or "N/A"
        jcr = raw_result.get("jcr")
        if jcr and jcr.get("category"):
            journal_type = jcr["category"]

        # Research field: not always populated in API, try fqb_jcr major_category
        research_field = raw_result.get("research_field") or ""
        if not research_field:
            fqb = raw_result.get("fqb_jcr")
            if fqb:
                parts = []
                if fqb.get("major_category"):
                    parts.append(fqb["major_category"])
                for i in range(1, 7):
                    sub = fqb.get(f"sub_category_{i}")
                    if sub:
                        parts.append(sub)
                research_field = "; ".join(parts)

        # DOI: prefer full URL format
        doi_raw = raw_result.get("doi") or ""
        doi = f"https://doi.org/{doi_raw}" if doi_raw and not doi_raw.startswith("http") else doi_raw

        return PaperInfo(
            title=raw_result.get("title") or "N/A",
            authors=raw_result.get("authors") or "N/A",
            affiliations=raw_result.get("affiliations") or "N/A",
            conference_journal=raw_result.get("conference_journal") or "N/A",
            conference_journal_type=journal_type,
            research_field=research_field or "N/A",
            doi=doi or "N/A",
            publication_date=raw_result.get("publication_date") or "N/A",
            abstract=raw_result.get("abstract_text") or raw_result.get("abstract_contents") or "N/A",
            citation_count=raw_result.get("citation_count", 0),
            source_url=raw_result.get("source_url") or raw_result.get("url") or "N/A",
        )

    async def search_papers(self, query: str, options: SearchOptions) -> list[PaperInfo]:
        """Search and return PaperInfo directly (zero-loss academic metadata).

        This is the preferred method for the OpenSift pipeline, bypassing
        the lossy StandardDocument conversion.

        Args:
            query: The search query string.
            options: Search behavior options.

        Returns:
            List of PaperInfo with full academic metadata.
        """
        raw = await self.search(query, options)
        return [self.map_to_paper(paper) for paper in raw.documents]

    async def health_check(self) -> AdapterHealth:
        """Check AtomWalker API health with a lightweight search."""
        if not self._client:
            return AdapterHealth(status="unhealthy", message="Client not initialized")

        try:
            start = time.monotonic()
            response = await self._client.get(
                f"/api/v1/resource/ScholarSearch/paper/{self._index}",
                params={"search": "test", "search_strategy": "fast", "size": 1},
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            if response.status_code == 200:
                return AdapterHealth(
                    status="healthy",
                    latency_ms=latency_ms,
                    last_check=datetime.now(UTC).isoformat(),
                    message=f"Index: {self._index}",
                )
            else:
                return AdapterHealth(
                    status="degraded",
                    latency_ms=latency_ms,
                    last_check=datetime.now(UTC).isoformat(),
                    message=f"HTTP {response.status_code}",
                )
        except Exception as e:
            return AdapterHealth(status="unhealthy", message=str(e))
