"""OpenSift Python SDK — Async and sync clients for the OpenSift REST API.

Usage::

    # Async
    async with AsyncOpenSiftClient("http://localhost:8080") as client:
        response = await client.search("solar nowcasting")

    # Sync (wraps async client internally)
    client = OpenSiftClient("http://localhost:8080")
    response = client.search("solar nowcasting")
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Coroutine, Iterator
from typing import Any, TypeVar, cast

import httpx

_T = TypeVar("_T")

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Response types (lightweight dicts — avoids coupling to server models)
# ═══════════════════════════════════════════════════════════════════════════════

SearchResult = dict[str, Any]
"""Complete search response dict (mirrors ``SearchResponse`` JSON)."""

StreamEvent = dict[str, Any]
"""A single SSE event dict with ``event`` and ``data`` keys."""

BatchResult = dict[str, Any]
"""Batch search response dict."""

PlanResult = dict[str, Any]
"""Plan-only response dict (mirrors ``PlanResponse`` JSON)."""


# ═══════════════════════════════════════════════════════════════════════════════
# Async client
# ═══════════════════════════════════════════════════════════════════════════════


class AsyncOpenSiftClient:
    """Async Python client for the OpenSift API.

    Args:
        base_url: OpenSift server URL, e.g. ``"http://localhost:8080"``.
        timeout: Request timeout in seconds.
        **httpx_kwargs: Additional keyword arguments passed to ``httpx.AsyncClient``.

    Example::

        async with AsyncOpenSiftClient("http://localhost:8080") as client:
            resp = await client.search("有哪些关于太阳能即时预报的深度学习论文?")
            for r in resp["perfect_results"]:
                print(r["result"]["title"])
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        *,
        timeout: float = 120.0,
        **httpx_kwargs: Any,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            **httpx_kwargs,
        )

    async def __aenter__(self) -> AsyncOpenSiftClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ── Health ──

    async def health(self) -> dict[str, Any]:
        """Check server health.

        Returns:
            Health status dict.
        """
        resp = await self._client.get("/v1/health")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def adapter_health(self) -> dict[str, Any]:
        """Check adapter health.

        Returns:
            Per-adapter health status dict.
        """
        resp = await self._client.get("/v1/health/adapters")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    # ── Plan (standalone) ──

    async def plan(
        self,
        query: str,
        *,
        decompose: bool = True,
    ) -> PlanResult:
        """Generate search queries and screening criteria (plan only).

        Runs only the query-planning stage without executing search or
        verification.

        Args:
            query: Natural language search query.
            decompose: Whether to decompose query into sub-queries.

        Returns:
            Plan response dict with ``request_id``, ``query``,
            ``criteria_result``, and ``processing_time_ms``.
        """
        payload: dict[str, Any] = {
            "query": query,
            "options": {
                "decompose": decompose,
            },
        }
        resp = await self._client.post("/v1/plan", json=payload)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    # ── Search (complete mode) ──

    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        verify: bool = True,
        decompose: bool = True,
        classify: bool = True,
        **extra_options: Any,
    ) -> SearchResult:
        """Execute an AI-enhanced search (complete mode).

        Waits for all results to be verified, then returns a single response.

        Args:
            query: Natural language search query.
            max_results: Maximum results to return.
            verify: Whether to run LLM verification.
            decompose: Whether to decompose query into sub-queries.
            classify: Whether to classify results (perfect/partial/reject).
                      When False, returns raw verification results without
                      classification in ``raw_results``.
            **extra_options: Additional options passed to ``SearchOptions``.

        Returns:
            Complete search response as a dict.
        """
        payload: dict[str, Any] = {
            "query": query,
            "options": {
                "max_results": max_results,
                "verify": verify,
                "decompose": decompose,
                "classify": classify,
                "stream": False,
                **extra_options,
            },
        }
        resp = await self._client.post("/v1/search", json=payload)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    # ── Search (streaming mode) ──

    async def search_stream(
        self,
        query: str,
        *,
        max_results: int = 10,
        verify: bool = True,
        decompose: bool = True,
        classify: bool = True,
        **extra_options: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Execute an AI-enhanced search (streaming mode).

        Yields SSE events as results are verified one by one.

        Args:
            query: Natural language search query.
            max_results: Maximum results to return.
            verify: Whether to run LLM verification.
            decompose: Whether to decompose query into sub-queries.
            classify: Whether to classify results. When False, each result
                      event carries ``raw_result`` instead of ``scored_result``.
            **extra_options: Additional options.

        Yields:
            StreamEvent dicts with ``event`` (str) and ``data`` (dict) keys.
        """
        payload: dict[str, Any] = {
            "query": query,
            "options": {
                "max_results": max_results,
                "verify": verify,
                "decompose": decompose,
                "classify": classify,
                "stream": True,
                **extra_options,
            },
        }
        async with self._client.stream("POST", "/v1/search", json=payload) as resp:
            resp.raise_for_status()
            async for event in _parse_sse_stream(resp):
                yield event

    # ── Batch search ──

    async def batch_search(
        self,
        queries: list[str],
        *,
        max_results: int = 10,
        verify: bool = True,
        decompose: bool = True,
        classify: bool = True,
        export_format: str | None = None,
        **extra_options: Any,
    ) -> BatchResult:
        """Execute multiple search queries in a single batch request.

        Args:
            queries: List of natural language queries.
            max_results: Maximum results per query.
            verify: Whether to run LLM verification.
            decompose: Whether to decompose queries.
            classify: Whether to classify results. When False, returns raw
                      verification results without classification.
            export_format: Optional export format (``"csv"`` or ``"json"``).
                           If set, the response includes a ``download_url``.
            **extra_options: Additional options.

        Returns:
            Batch search response as a dict.
        """
        payload: dict[str, Any] = {
            "queries": queries,
            "options": {
                "max_results": max_results,
                "verify": verify,
                "decompose": decompose,
                "classify": classify,
                **extra_options,
            },
        }
        if export_format:
            payload["export_format"] = export_format

        resp = await self._client.post("/v1/search/batch", json=payload)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())


# ═══════════════════════════════════════════════════════════════════════════════
# Sync client (wraps AsyncOpenSiftClient)
# ═══════════════════════════════════════════════════════════════════════════════


class OpenSiftClient:
    """Synchronous Python client for the OpenSift API.

    Wraps :class:`AsyncOpenSiftClient` using ``asyncio.run``.

    Args:
        base_url: OpenSift server URL.
        timeout: Request timeout in seconds.
        **httpx_kwargs: Additional keyword arguments passed to ``httpx.AsyncClient``.

    Example::

        client = OpenSiftClient("http://localhost:8080")
        resp = client.search("solar nowcasting deep learning")
        print(resp["perfect_results"])
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        *,
        timeout: float = 120.0,
        **httpx_kwargs: Any,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._httpx_kwargs = httpx_kwargs

    def _run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Run an async coroutine synchronously."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop (e.g. Jupyter) — use nest_asyncio or thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def _make_client(self) -> AsyncOpenSiftClient:
        return AsyncOpenSiftClient(
            self._base_url,
            timeout=self._timeout,
            **self._httpx_kwargs,
        )

    def health(self) -> dict[str, Any]:
        """Check server health."""

        async def _call() -> dict[str, Any]:
            async with self._make_client() as c:
                return await c.health()

        return self._run(_call())

    def adapter_health(self) -> dict[str, Any]:
        """Check adapter health."""

        async def _call() -> dict[str, Any]:
            async with self._make_client() as c:
                return await c.adapter_health()

        return self._run(_call())

    def plan(
        self,
        query: str,
        *,
        decompose: bool = True,
    ) -> PlanResult:
        """Generate search queries and screening criteria (plan only)."""

        async def _call() -> PlanResult:
            async with self._make_client() as c:
                return await c.plan(query, decompose=decompose)

        return self._run(_call())

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        verify: bool = True,
        decompose: bool = True,
        classify: bool = True,
        **extra_options: Any,
    ) -> SearchResult:
        """Execute an AI-enhanced search (complete mode)."""

        async def _call() -> SearchResult:
            async with self._make_client() as c:
                return await c.search(
                    query,
                    max_results=max_results,
                    verify=verify,
                    decompose=decompose,
                    classify=classify,
                    **extra_options,
                )

        return self._run(_call())

    def search_stream(
        self,
        query: str,
        *,
        max_results: int = 10,
        verify: bool = True,
        decompose: bool = True,
        classify: bool = True,
        **extra_options: Any,
    ) -> Iterator[StreamEvent]:
        """Execute an AI-enhanced search (streaming mode).

        Returns an iterator of SSE events.
        """

        async def _collect() -> list[StreamEvent]:
            events: list[StreamEvent] = []
            async with self._make_client() as c:
                async for ev in c.search_stream(
                    query,
                    max_results=max_results,
                    verify=verify,
                    decompose=decompose,
                    classify=classify,
                    **extra_options,
                ):
                    events.append(ev)
            return events

        return iter(self._run(_collect()))

    def batch_search(
        self,
        queries: list[str],
        *,
        max_results: int = 10,
        verify: bool = True,
        decompose: bool = True,
        classify: bool = True,
        export_format: str | None = None,
        **extra_options: Any,
    ) -> BatchResult:
        """Execute multiple search queries in a single batch."""

        async def _call() -> BatchResult:
            async with self._make_client() as c:
                return await c.batch_search(
                    queries,
                    max_results=max_results,
                    verify=verify,
                    decompose=decompose,
                    classify=classify,
                    export_format=export_format,
                    **extra_options,
                )

        return self._run(_call())


# ═══════════════════════════════════════════════════════════════════════════════
# SSE parser
# ═══════════════════════════════════════════════════════════════════════════════


async def _parse_sse_stream(response: httpx.Response) -> AsyncIterator[StreamEvent]:
    """Parse an SSE event stream from an httpx response.

    Yields:
        Dicts with ``event`` and ``data`` keys.
    """
    event_type: str = ""
    data_lines: list[str] = []

    async for line in response.aiter_lines():
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
        elif line == "" and event_type:
            # Empty line = end of event
            raw_data = "\n".join(data_lines)
            try:
                parsed = json.loads(raw_data)
            except json.JSONDecodeError:
                parsed = {"raw": raw_data}
            yield {"event": event_type, "data": parsed}
            event_type = ""
            data_lines = []
