"""Apache Solr adapter — Full-text search via Solr's JSON Request API.

Connects to Apache Solr (v8+) using ``httpx`` (async) over the standard
JSON Request API.  No extra dependencies beyond ``httpx`` (already a
core OpenSift dependency) are required.

Usage::

    adapter = SolrAdapter(
        base_url="http://localhost:8983/solr",
        collection="documents",
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


class SolrAdapter(SearchAdapter):
    """Search adapter for Apache Solr (v8+).

    Communicates with Solr via its `JSON Request API`_ over HTTP.

    .. _JSON Request API: https://solr.apache.org/guide/solr/latest/query-guide/json-request-api.html

    Supports:
      - Full-text search (``edismax`` query parser)
      - Highlighting
      - Recency filtering via ``fq``

    Args:
        base_url: Solr base URL, e.g. ``"http://localhost:8983/solr"``.
        collection: Default Solr collection/core name.
        username: Optional basic-auth username.
        password: Optional basic-auth password.
        api_key: Not used by Solr; accepted for interface consistency.
        timeout: HTTP request timeout in seconds.
        **kwargs: Extra keyword arguments stored for future use.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8983/solr",
        collection: str = "documents",
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._collection = collection
        self._username = username
        self._password = password
        self._timeout = timeout
        self._extra_kwargs = kwargs
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "solr"

    async def initialize(self) -> None:
        """Create an ``httpx.AsyncClient`` and ping the Solr admin API."""
        auth = None
        if self._username and self._password:
            auth = httpx.BasicAuth(self._username, self._password)

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
            auth=auth,
        )

        try:
            resp = await self._client.get(f"/{self._collection}/admin/ping")
            resp.raise_for_status()
            logger.info(
                "Connected to Solr collection '%s' at %s",
                self._collection,
                self._base_url,
            )
        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to connect to Solr: {e}") from e

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Search ───────────────────────────────────────────────────────────

    async def search(self, query: str, options: SearchOptions) -> RawResults:
        """Execute a search query against Solr using the JSON Request API."""
        if not self._client:
            raise ConnectionError("Solr client not initialized.")

        # Build the JSON request body for Solr's /select handler
        params: dict[str, Any] = {
            "query": query,
            "limit": options.max_results,
            "offset": 0,
            "params": {
                "defType": "edismax",
                "qf": "title^2 content description",
                "fl": "*, score",
                "hl": "true",
                "hl.fl": "title,content",
                "hl.fragsize": 200,
                "hl.snippets": 3,
            },
        }

        # Recency filter via fq
        if options.recency_filter:
            fq = self._parse_recency_filter(options.recency_filter)
            if fq:
                params["filter"] = [fq]

        try:
            start = time.monotonic()
            resp = await self._client.post(
                f"/{self._collection}/select",
                json=params,
            )
            resp.raise_for_status()
            took_ms = int((time.monotonic() - start) * 1000)

            data = resp.json()
            response_section = data.get("response", {})
            total_hits = response_section.get("numFound", 0)
            docs = response_section.get("docs", [])

            # Attach highlighting to each doc for downstream mapping
            highlighting = data.get("highlighting", {})
            for doc in docs:
                doc_id = doc.get("id", "")
                if doc_id in highlighting:
                    doc["_highlighting"] = highlighting[doc_id]

            return RawResults(
                total_hits=total_hits,
                documents=docs,
                metadata={"qtime_ms": data.get("responseHeader", {}).get("QTime", 0)},
                took_ms=took_ms,
            )
        except httpx.HTTPError as e:
            raise QueryError(f"Solr query failed: {e}") from e

    async def fetch_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve a single document from Solr by its ``id`` field."""
        if not self._client:
            raise ConnectionError("Solr client not initialized.")

        try:
            resp = await self._client.get(
                f"/{self._collection}/get",
                params={"id": doc_id},
            )
            resp.raise_for_status()
            data = resp.json()
            doc = data.get("doc")
            if doc is None:
                raise DocumentNotFoundError(f"Document '{doc_id}' not found.")
            return dict(doc)
        except DocumentNotFoundError:
            raise
        except httpx.HTTPError as e:
            raise QueryError(f"Failed to fetch document from Solr: {e}") from e

    # ── Schema mapping ───────────────────────────────────────────────────

    def map_to_standard_schema(self, raw_result: dict[str, Any]) -> StandardDocument:
        """Map a Solr document to ``StandardDocument``.

        Solr documents are flat key-value dicts.  Common field names are
        mapped; anything else lands in ``metadata.extra``.
        """
        doc_id = str(raw_result.get("id", ""))
        title = self._first_value(raw_result.get("title", "Untitled"))
        content = self._first_value(raw_result.get("content", raw_result.get("body", raw_result.get("text", ""))))

        # Build snippet from highlighting
        hl = raw_result.get("_highlighting", {})
        snippet_parts: list[str] = []
        for fragments in hl.values():
            if isinstance(fragments, list):
                snippet_parts.extend(fragments)
        snippet = " ... ".join(snippet_parts) if snippet_parts else None

        # Published date
        published_date = None
        date_str = raw_result.get("published_date") or raw_result.get("date") or raw_result.get("timestamp")
        if date_str:
            import contextlib

            with contextlib.suppress(ValueError, TypeError):
                published_date = datetime.fromisoformat(str(self._first_value(date_str)).replace("Z", "+00:00"))

        author = self._first_value(raw_result.get("author"))
        url = self._first_value(raw_result.get("url"))
        tags_raw = raw_result.get("tags", raw_result.get("category", []))
        tags = tags_raw if isinstance(tags_raw, list) else [str(tags_raw)] if tags_raw else []

        return StandardDocument(
            id=doc_id,
            title=title,
            content=content,
            snippet=snippet,
            score=raw_result.get("score", 0.0),
            metadata=DocumentMetadata(
                source=self._collection,
                url=url,
                published_date=published_date,
                author=author,
                tags=tags,
                extra={"solr_collection": self._collection},
            ),
        )

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> AdapterHealth:
        """Ping the Solr admin endpoint."""
        if not self._client:
            return AdapterHealth(status="unhealthy", message="Client not initialized")

        try:
            start = time.monotonic()
            resp = await self._client.get(f"/{self._collection}/admin/ping")
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                solr_status = data.get("status", "unknown")
                return AdapterHealth(
                    status="healthy" if solr_status == "OK" else "degraded",
                    latency_ms=latency_ms,
                    last_check=datetime.now(UTC).isoformat(),
                    message=f"Collection: {self._collection}, status: {solr_status}",
                )
            return AdapterHealth(
                status="degraded",
                latency_ms=latency_ms,
                last_check=datetime.now(UTC).isoformat(),
                message=f"Solr returned HTTP {resp.status_code}",
            )
        except Exception as e:
            return AdapterHealth(status="unhealthy", message=str(e))

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _first_value(val: Any) -> Any:
        """Solr may return single-valued fields as lists; unwrap transparently."""
        if isinstance(val, list):
            return val[0] if val else ""
        return val

    @staticmethod
    def _parse_recency_filter(recency: str) -> str | None:
        """Convert a recency string (``'1y'``, ``'30d'``) to a Solr ``fq`` clause."""
        mapping = {"y": "YEAR", "m": "MONTH", "w": "DAY", "d": "DAY", "h": "HOUR"}
        if len(recency) < 2:
            return None
        unit = recency[-1].lower()
        if unit not in mapping:
            return None
        try:
            value = int(recency[:-1])
        except ValueError:
            return None

        # Convert to days for 'w'
        if unit == "w":
            value *= 7

        return f"timestamp:[NOW-{value}{mapping[unit]}S TO NOW]"
