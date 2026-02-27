"""OpenSearch adapter — Full-text and vector search for OpenSearch (v2+).

OpenSearch is an AWS-maintained fork of Elasticsearch with a compatible
query DSL and API surface.  This adapter uses ``opensearch-py`` (async)
and provides search, document retrieval, and health monitoring through
the standard OpenSift adapter interface.

Install the optional dependency::

    pip install opensift[opensearch]
    # or: pip install opensearch-py
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from opensift.adapters.base.adapter import AdapterHealth, RawResults, SearchAdapter
from opensift.adapters.base.exceptions import (
    ConfigurationError,
    ConnectionError,
    DocumentNotFoundError,
    QueryError,
)
from opensift.models.document import DocumentMetadata, StandardDocument
from opensift.models.query import SearchOptions

logger = logging.getLogger(__name__)


class OpenSearchAdapter(SearchAdapter):
    """Search adapter for OpenSearch (v2+).

    Supports:
      - Full-text search (BM25)
      - Highlighting
      - Recency filtering

    The query DSL is largely compatible with Elasticsearch, but this
    adapter uses the ``opensearchpy`` client library for native support.

    Args:
        hosts: List of OpenSearch node URLs.
        index_pattern: Index pattern for searches (e.g., ``'docs-*'``).
        username: Optional HTTP basic-auth username.
        password: Optional HTTP basic-auth password.
        api_key: Optional API key (``(id, api_key)`` tuple or encoded string).
        verify_certs: Whether to verify TLS certificates.
        **kwargs: Additional keyword arguments forwarded to ``AsyncOpenSearch``.
    """

    def __init__(
        self,
        hosts: list[str] | None = None,
        index_pattern: str = "*",
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        verify_certs: bool = True,
        **kwargs: Any,
    ) -> None:
        self._hosts = hosts or ["https://localhost:9200"]
        self._index_pattern = index_pattern
        self._username = username
        self._password = password
        self._api_key = api_key
        self._verify_certs = verify_certs
        self._extra_kwargs = kwargs
        self._client: Any = None

    @property
    def name(self) -> str:
        return "opensearch"

    async def initialize(self) -> None:
        """Create and verify the ``AsyncOpenSearch`` client."""
        try:
            from opensearchpy import AsyncOpenSearch
        except ImportError as e:
            raise ConfigurationError(
                "opensearch-py package is required.  Install with: pip install opensift[opensearch]"
            ) from e

        client_kwargs: dict[str, Any] = {
            "hosts": self._hosts,
            "verify_certs": self._verify_certs,
            "ssl_show_warn": False,
        }
        if self._username and self._password:
            client_kwargs["http_auth"] = (self._username, self._password)

        client_kwargs.update(self._extra_kwargs)

        try:
            self._client = AsyncOpenSearch(**client_kwargs)
            info = await self._client.info()
            version = info.get("version", {}).get("number", "unknown")
            cluster = info.get("cluster_name", "unknown")
            logger.info("Connected to OpenSearch cluster: %s (v%s)", cluster, version)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to OpenSearch: {e}") from e

    async def shutdown(self) -> None:
        """Close the OpenSearch client."""
        if self._client:
            await self._client.close()
            self._client = None

    # ── Search ───────────────────────────────────────────────────────────

    async def search(self, query: str, options: SearchOptions) -> RawResults:
        """Execute a full-text query against OpenSearch."""
        if not self._client:
            raise ConnectionError("OpenSearch client not initialized.")

        body: dict[str, Any] = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^2", "content", "description"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            },
            "size": options.max_results,
            "highlight": {
                "fields": {
                    "content": {"fragment_size": 200, "number_of_fragments": 3},
                    "title": {},
                }
            },
            "_source": True,
        }

        if options.recency_filter:
            range_filter = self._parse_recency_filter(options.recency_filter)
            if range_filter:
                body["query"] = {
                    "bool": {
                        "must": [body["query"]],
                        "filter": [range_filter],
                    }
                }

        try:
            start = time.monotonic()
            response = await self._client.search(index=self._index_pattern, body=body)
            took_ms = int((time.monotonic() - start) * 1000)

            hits = response.get("hits", {})
            total = hits.get("total", {}).get("value", 0)
            documents = list(hits.get("hits", []))

            return RawResults(
                total_hits=total,
                documents=documents,
                metadata={"took_os_ms": response.get("took", 0)},
                took_ms=took_ms,
            )
        except Exception as e:
            raise QueryError(f"OpenSearch query failed: {e}") from e

    async def fetch_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve a single document by ID."""
        if not self._client:
            raise ConnectionError("OpenSearch client not initialized.")
        try:
            response = await self._client.get(index=self._index_pattern, id=doc_id)
            return dict(response)
        except Exception as e:
            if "NotFoundError" in type(e).__name__:
                raise DocumentNotFoundError(f"Document '{doc_id}' not found.") from e
            raise QueryError(f"Failed to fetch document: {e}") from e

    # ── Schema mapping ───────────────────────────────────────────────────

    def map_to_standard_schema(self, raw_result: dict[str, Any]) -> StandardDocument:
        """Map an OpenSearch hit to ``StandardDocument``."""
        source = raw_result.get("_source", {})
        highlight = raw_result.get("highlight", {})

        snippet_parts: list[str] = []
        for field_highlights in highlight.values():
            if isinstance(field_highlights, list):
                snippet_parts.extend(field_highlights)
        snippet = " ... ".join(snippet_parts) if snippet_parts else None

        published_date = None
        date_str = source.get("published_date") or source.get("date") or source.get("@timestamp")
        if date_str:
            import contextlib

            with contextlib.suppress(ValueError, TypeError):
                published_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))

        return StandardDocument(
            id=raw_result.get("_id", ""),
            title=source.get("title", "Untitled"),
            content=source.get("content", source.get("body", source.get("text", ""))),
            snippet=snippet,
            score=raw_result.get("_score", 0.0),
            metadata=DocumentMetadata(
                source=raw_result.get("_index", "unknown"),
                url=source.get("url"),
                published_date=published_date,
                author=source.get("author"),
                tags=source.get("tags", []),
                extra={"os_index": raw_result.get("_index")},
            ),
        )

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> AdapterHealth:
        """Check OpenSearch cluster health."""
        if not self._client:
            return AdapterHealth(status="unhealthy", message="Client not initialized")

        try:
            start = time.monotonic()
            health = await self._client.cluster.health()
            latency_ms = int((time.monotonic() - start) * 1000)

            status_map = {"green": "healthy", "yellow": "degraded", "red": "unhealthy"}

            return AdapterHealth(
                status=status_map.get(health.get("status", "red"), "unhealthy"),
                latency_ms=latency_ms,
                last_check=datetime.now(UTC).isoformat(),
                message=f"Cluster: {health.get('cluster_name')}, Nodes: {health.get('number_of_nodes')}",
            )
        except Exception as e:
            return AdapterHealth(status="unhealthy", message=str(e))

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_recency_filter(recency: str) -> dict[str, Any] | None:
        """Parse a recency string (e.g. ``'1y'``, ``'30d'``) to an OpenSearch range filter."""
        mapping = {"y": "year", "m": "month", "w": "week", "d": "day", "h": "hour"}
        if len(recency) < 2:
            return None
        unit = recency[-1].lower()
        if unit not in mapping:
            return None
        try:
            value = int(recency[:-1])
        except ValueError:
            return None

        es_unit = mapping[unit]
        return {"range": {"@timestamp": {"gte": f"now-{value}{recency[-1]}/{es_unit}"}}}
