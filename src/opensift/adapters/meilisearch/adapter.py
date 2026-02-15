"""MeiliSearch adapter — Modern, developer-friendly search connector.

MeiliSearch provides instant, typo-tolerant search out of the box.
This adapter communicates via the official REST API using ``httpx``.
No extra dependencies beyond ``httpx`` (already a core OpenSift
dependency) are required.

Usage::

    adapter = MeiliSearchAdapter(
        base_url="http://localhost:7700",
        index="documents",
        api_key="your-master-key",
    )
    await adapter.initialize()
    results = await adapter.search("solar nowcasting", options)
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from opensift.adapters.base.adapter import AdapterHealth, RawResults, SearchAdapter
from opensift.adapters.base.exceptions import (
    ConnectionError,
    DocumentNotFoundError,
    QueryError,
)
from opensift.models.document import DocumentMetadata, StandardDocument
from opensift.models.query import SearchOptions

logger = logging.getLogger(__name__)


class MeiliSearchAdapter(SearchAdapter):
    """Search adapter for MeiliSearch.

    Communicates with MeiliSearch via its `REST API`_ over HTTP.

    .. _REST API: https://www.meilisearch.com/docs/reference/api/overview

    Supports:
      - Instant full-text search with typo tolerance
      - Filtering and sorting
      - Highlighting / crop

    Args:
        base_url: MeiliSearch instance URL, e.g. ``"http://localhost:7700"``.
        index: Default MeiliSearch index name (UID).
        api_key: Master key or API key for authentication.
        timeout: HTTP request timeout in seconds.
        **kwargs: Extra keyword arguments stored for future use.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7700",
        index: str = "documents",
        api_key: str | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._index = index
        self._api_key = api_key
        self._timeout = timeout
        self._extra_kwargs = kwargs
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "meilisearch"

    async def initialize(self) -> None:
        """Create an ``httpx.AsyncClient`` and verify connection to MeiliSearch."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
            headers=headers,
        )

        try:
            resp = await self._client.get("/health")
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "available":
                raise ConnectionError(f"MeiliSearch not available: {data}")
            logger.info(
                "Connected to MeiliSearch at %s (index: %s)",
                self._base_url,
                self._index,
            )
        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to connect to MeiliSearch: {e}") from e

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Search ───────────────────────────────────────────────────────────

    async def search(self, query: str, options: SearchOptions) -> RawResults:
        """Execute a search query against MeiliSearch.

        Uses the ``/indexes/{index}/search`` endpoint.
        """
        if not self._client:
            raise ConnectionError("MeiliSearch client not initialized.")

        payload: dict[str, Any] = {
            "q": query,
            "limit": options.max_results,
            "offset": 0,
            "attributesToHighlight": ["title", "content"],
            "highlightPreTag": "<em>",
            "highlightPostTag": "</em>",
            "attributesToCrop": ["content"],
            "cropLength": 200,
            "showRankingScore": True,
        }

        # Recency filter
        if options.recency_filter:
            filter_str = self._parse_recency_filter(options.recency_filter)
            if filter_str:
                payload["filter"] = filter_str

        try:
            start = time.monotonic()
            resp = await self._client.post(
                f"/indexes/{self._index}/search",
                json=payload,
            )
            resp.raise_for_status()
            took_ms = int((time.monotonic() - start) * 1000)

            data = resp.json()
            hits = data.get("hits", [])
            total_hits = data.get("estimatedTotalHits", data.get("totalHits", len(hits)))

            return RawResults(
                total_hits=total_hits,
                documents=hits,
                metadata={
                    "processing_time_ms": data.get("processingTimeMs", 0),
                    "query": data.get("query", query),
                },
                took_ms=took_ms,
            )
        except httpx.HTTPError as e:
            raise QueryError(f"MeiliSearch query failed: {e}") from e

    async def fetch_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve a single document from MeiliSearch by its primary key."""
        if not self._client:
            raise ConnectionError("MeiliSearch client not initialized.")

        try:
            resp = await self._client.get(f"/indexes/{self._index}/documents/{doc_id}")
            if resp.status_code == 404:
                raise DocumentNotFoundError(f"Document '{doc_id}' not found.")
            resp.raise_for_status()
            return resp.json()
        except DocumentNotFoundError:
            raise
        except httpx.HTTPError as e:
            raise QueryError(f"Failed to fetch document from MeiliSearch: {e}") from e

    # ── Schema mapping ───────────────────────────────────────────────────

    def map_to_standard_schema(self, raw_result: dict[str, Any]) -> StandardDocument:
        """Map a MeiliSearch hit to ``StandardDocument``.

        MeiliSearch returns flat document objects with an optional
        ``_formatted`` key for highlighted fields.
        """
        doc_id = str(raw_result.get("id", ""))
        title = raw_result.get("title", "Untitled")
        content = raw_result.get("content", raw_result.get("body", raw_result.get("text", "")))

        # Snippet from formatted (highlighted) content
        formatted = raw_result.get("_formatted", {})
        snippet = formatted.get("content", formatted.get("body"))

        # Score
        score = raw_result.get("_rankingScore", 0.0)

        # Published date
        published_date = None
        date_str = raw_result.get("published_date") or raw_result.get("date") or raw_result.get("timestamp")
        if date_str:
            import contextlib

            with contextlib.suppress(ValueError, TypeError):
                published_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))

        return StandardDocument(
            id=doc_id,
            title=title,
            content=content,
            snippet=snippet,
            score=score,
            metadata=DocumentMetadata(
                source=self._index,
                url=raw_result.get("url"),
                published_date=published_date,
                author=raw_result.get("author"),
                tags=raw_result.get("tags", []),
                extra={"meili_index": self._index},
            ),
        )

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> AdapterHealth:
        """Check MeiliSearch health."""
        if not self._client:
            return AdapterHealth(status="unhealthy", message="Client not initialized")

        try:
            start = time.monotonic()
            resp = await self._client.get("/health")
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "unknown")
                return AdapterHealth(
                    status="healthy" if status == "available" else "degraded",
                    latency_ms=latency_ms,
                    last_check=datetime.now(UTC).isoformat(),
                    message=f"Index: {self._index}, status: {status}",
                )
            return AdapterHealth(
                status="degraded",
                latency_ms=latency_ms,
                last_check=datetime.now(UTC).isoformat(),
                message=f"MeiliSearch returned HTTP {resp.status_code}",
            )
        except Exception as e:
            return AdapterHealth(status="unhealthy", message=str(e))

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_recency_filter(recency: str) -> str | None:
        """Convert a recency string to a MeiliSearch filter expression.

        MeiliSearch filters work on numeric timestamps, so we convert
        the recency to a UNIX epoch threshold::

            "timestamp > 1700000000"

        Returns:
            A MeiliSearch filter string, or ``None`` if parsing fails.
        """
        import calendar
        from datetime import timedelta

        mapping = {"y": 365, "m": 30, "w": 7, "d": 1, "h": 0}
        if len(recency) < 2:
            return None
        unit = recency[-1].lower()
        if unit not in mapping:
            return None
        try:
            value = int(recency[:-1])
        except ValueError:
            return None

        delta = timedelta(hours=value) if unit == "h" else timedelta(days=value * mapping[unit])

        threshold = datetime.now(UTC) - delta
        ts = calendar.timegm(threshold.timetuple())
        return f"timestamp > {ts}"
