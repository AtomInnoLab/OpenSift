"""Wikipedia adapter — Search across Wikipedia articles via the wikipedia-api library.

Uses the ``wikipedia-api`` Python package to query Wikipedia's MediaWiki API.
Supports multi-language search (default: English) and returns article
summaries as search results for the OpenSift verification pipeline.

Install the optional dependency::

    pip install wikipedia-api

Usage::

    adapter = WikipediaAdapter(language="en", max_chars=2000)
    await adapter.initialize()
    results = await adapter.search("solar nowcasting", options)

API Reference: https://wikipedia-api.readthedocs.io/en/latest/
"""

from __future__ import annotations

import asyncio
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

_USER_AGENT = "OpenSift/0.1 (https://github.com/opensift/opensift; opensift@example.com)"


class WikipediaAdapter(SearchAdapter):
    """Search adapter for Wikipedia via the ``wikipedia-api`` library.

    Since Wikipedia doesn't expose a traditional full-text search API,
    this adapter uses Wikipedia's built-in search generator to discover
    pages matching a query, then fetches their summaries.

    Args:
        language: Wikipedia language code (e.g. ``"en"``, ``"zh"``, ``"de"``).
        max_chars: Maximum characters to include from each article summary.
        user_agent: User-agent string for Wikipedia API requests.
        **kwargs: Extra keyword arguments (ignored, for config compat).
    """

    def __init__(
        self,
        language: str = "en",
        max_chars: int = 2000,
        user_agent: str = _USER_AGENT,
        **kwargs: Any,
    ) -> None:
        self._language = language
        self._max_chars = max_chars
        self._user_agent = user_agent
        self._wiki: Any = None  # wikipediaapi.Wikipedia instance
        self._extra_kwargs = kwargs

    @property
    def name(self) -> str:
        return "wikipedia"

    async def initialize(self) -> None:
        """Initialise the wikipedia-api client.

        Raises:
            ConfigurationError: If the ``wikipedia-api`` package is not installed.
        """
        try:
            import wikipediaapi
        except ImportError as e:
            raise ConfigurationError(
                "The 'wikipedia-api' package is required for the Wikipedia adapter. "
                "Install it with: pip install wikipedia-api"
            ) from e

        self._wiki = wikipediaapi.Wikipedia(
            user_agent=self._user_agent,
            language=self._language,
        )
        logger.info(
            "Wikipedia adapter initialized (language=%s, max_chars=%d)",
            self._language,
            self._max_chars,
        )

    async def shutdown(self) -> None:
        """Release resources (no persistent connections to close)."""
        self._wiki = None

    # ── Search ───────────────────────────────────────────────────────────

    async def search(self, query: str, options: SearchOptions) -> RawResults:
        """Search Wikipedia for articles matching *query*.

        Uses the MediaWiki ``opensearch`` API endpoint to find matching
        page titles, then fetches summary + metadata for each page.

        Args:
            query: The search query string.
            options: Search behaviour options.

        Returns:
            RawResults containing Wikipedia article dicts.
        """
        if self._wiki is None:
            raise ConnectionError("Wikipedia adapter not initialized.")

        try:
            start = time.monotonic()

            # Run the blocking wikipedia-api calls in a thread pool
            loop = asyncio.get_running_loop()
            documents = await loop.run_in_executor(
                None,
                self._search_sync,
                query,
                options.max_results,
            )

            took_ms = int((time.monotonic() - start) * 1000)

            logger.debug(
                "Wikipedia search: query=%s, results=%d, took=%dms",
                query,
                len(documents),
                took_ms,
            )

            return RawResults(
                total_hits=len(documents),
                documents=documents,
                metadata={
                    "language": self._language,
                    "query": query,
                },
                took_ms=took_ms,
            )
        except Exception as e:
            if isinstance(e, ConnectionError | QueryError):
                raise
            raise QueryError(f"Wikipedia search failed: {e}") from e

    def _search_sync(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Synchronous search implementation (runs in executor).

        Uses MediaWiki opensearch API to find page titles, then fetches
        each page's summary and metadata via wikipedia-api.
        """
        import json as json_mod
        import urllib.parse
        import urllib.request

        # Step 1: Use MediaWiki opensearch to get page titles
        encoded_query = urllib.parse.quote(query)
        search_url = (
            f"https://{self._language}.wikipedia.org/w/api.php"
            f"?action=opensearch&search={encoded_query}"
            f"&limit={max_results}&namespace=0&format=json"
        )
        req = urllib.request.Request(search_url, headers={"User-Agent": self._user_agent})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json_mod.loads(resp.read().decode("utf-8"))

        # opensearch returns: [query, [titles], [descriptions], [urls]]
        if len(data) < 4:
            return []

        titles: list[str] = data[1]
        urls: list[str] = data[3]

        # Step 2: Fetch each page via wikipedia-api for rich content
        documents: list[dict[str, Any]] = []
        for i, title in enumerate(titles):
            page = self._wiki.page(title)
            if not page.exists():
                continue

            summary = page.summary or ""
            if len(summary) > self._max_chars:
                summary = summary[: self._max_chars] + "…"

            # Collect categories
            categories = [cat.replace("Category:", "") for cat in page.categories]

            # Collect language links count
            langlinks_count = len(page.langlinks) if page.langlinks else 0

            doc: dict[str, Any] = {
                "id": f"wiki_{self._language}_{page.pageid}"
                if hasattr(page, "pageid")
                else f"wiki_{self._language}_{i}",
                "title": page.title,
                "summary": summary,
                "full_url": page.fullurl,
                "canonical_url": page.canonicalurl,
                "language": self._language,
                "categories": categories[:10],
                "langlinks_count": langlinks_count,
                "url": urls[i] if i < len(urls) else page.fullurl,
            }
            documents.append(doc)

        return documents

    async def fetch_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve a single Wikipedia page by title.

        Args:
            doc_id: The Wikipedia page title.

        Returns:
            Raw page data as a dictionary.
        """
        if self._wiki is None:
            raise ConnectionError("Wikipedia adapter not initialized.")

        loop = asyncio.get_running_loop()
        page = await loop.run_in_executor(None, self._wiki.page, doc_id)

        if not page.exists():
            raise DocumentNotFoundError(f"Wikipedia page not found: {doc_id}")

        summary = page.summary or ""
        if len(summary) > self._max_chars:
            summary = summary[: self._max_chars] + "…"

        categories = [cat.replace("Category:", "") for cat in page.categories]

        return {
            "id": f"wiki_{self._language}_{doc_id}",
            "title": page.title,
            "summary": summary,
            "full_url": page.fullurl,
            "canonical_url": page.canonicalurl,
            "language": self._language,
            "categories": categories[:10],
            "url": page.fullurl,
        }

    # ── Schema mapping ───────────────────────────────────────────────────

    def map_to_standard_schema(self, raw_result: dict[str, Any]) -> StandardDocument:
        """Map a Wikipedia article dict to ``StandardDocument``."""
        doc_id = str(raw_result.get("id", ""))
        title = raw_result.get("title", "Untitled")
        summary = raw_result.get("summary", "")
        url = raw_result.get("url") or raw_result.get("full_url", "")
        categories = raw_result.get("categories", [])
        language = raw_result.get("language", self._language)

        return StandardDocument(
            id=doc_id,
            title=title,
            content=summary,
            snippet=summary[:200] if summary else None,
            score=1.0,  # Wikipedia doesn't provide relevance scores
            metadata=DocumentMetadata(
                source=f"wikipedia_{language}",
                url=url,
                published_date=None,
                author=None,
                language=language,
                tags=categories,
                extra={
                    "langlinks_count": raw_result.get("langlinks_count", 0),
                    "canonical_url": raw_result.get("canonical_url", ""),
                },
            ),
        )

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> AdapterHealth:
        """Check Wikipedia API connectivity."""
        if self._wiki is None:
            return AdapterHealth(status="unhealthy", message="Wikipedia client not initialized")

        try:
            start = time.monotonic()
            loop = asyncio.get_running_loop()
            page = await loop.run_in_executor(None, self._wiki.page, "Python_(programming_language)")
            latency_ms = int((time.monotonic() - start) * 1000)

            if page.exists():
                return AdapterHealth(
                    status="healthy",
                    latency_ms=latency_ms,
                    last_check=datetime.now(UTC).isoformat(),
                    message=f"Wikipedia ({self._language}) OK",
                )
            return AdapterHealth(
                status="degraded",
                latency_ms=latency_ms,
                last_check=datetime.now(UTC).isoformat(),
                message="Health check page not found",
            )
        except Exception as e:
            return AdapterHealth(status="unhealthy", message=str(e))
