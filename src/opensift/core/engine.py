"""OpenSift Engine — Core orchestrator for the search filtering funnel.

The engine manages the full request lifecycle:
  1. Query Planning: Generate search queries + screening criteria (LLM)
  2. Search Execution: Retrieve results via adapters
  3. Result Verification: Validate each result against criteria (LLM)
  4. Classification: Classify results as perfect / partial / reject
  5. Response Assembly

Supports two output modes:
  - **Complete** (``search``) — Returns a single ``SearchResponse``.
  - **Streaming** (``search_stream``) — Yields ``StreamEvent`` objects as
    results are verified one by one.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from opensift.adapters.base.registry import AdapterRegistry
from opensift.core.classifier import ResultClassifier
from opensift.core.planner import QueryPlanner
from opensift.core.verifier import EvidenceVerifier
from opensift.models.assessment import ResultClassification, ValidationResult
from opensift.models.query import BatchSearchRequest, SearchRequest
from opensift.models.response import BatchSearchResponse, PlanResponse, RawVerifiedResult, SearchResponse, StreamEvent
from opensift.models.result import ResultItem

if TYPE_CHECKING:
    from opensift.config.settings import Settings

logger = logging.getLogger(__name__)


def _detect_language(text: str) -> str:
    """Detect if text is primarily Chinese or English.

    Simple heuristic based on CJK character ratio.
    """
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return "中文" if cjk_count > len(text) * 0.1 else "English"


class OpenSiftEngine:
    """Core orchestrator for the OpenSift search filtering funnel.

    Pipeline:
      User Query → [Planner] → search_queries + criteria
                 → [Adapters] → results
                 → [Verifier] → per-result assessments
                 → [Classifier] → perfect / partial / reject
                 → SearchResponse  (complete mode)
                 → StreamEvent*    (streaming mode)

    Attributes:
        settings: Application configuration.
        planner: Criteria generation planner.
        verifier: Result validation verifier.
        adapter_registry: Registry of search adapters.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.planner = QueryPlanner(settings)
        self.verifier = EvidenceVerifier(settings)
        self.adapter_registry = AdapterRegistry()

    async def initialize(self) -> None:
        """Initialize all engine components (including LLM connectivity check)."""
        # Verify LLM connectivity for planner and verifier
        if self.planner._llm_client:
            ok = await self.planner._llm_client.verify_connection(
                model=self.settings.ai.model_planner,
            )
            if not ok:
                logger.error(
                    "Planner LLM connectivity check FAILED — planning will fall back to heuristics. "
                    "Check AI__API_KEY, AI__BASE_URL, and AI__MODEL_PLANNER settings."
                )
        if self.verifier._llm_client:
            ok = await self.verifier._llm_client.verify_connection(
                model=self.settings.ai.model_verifier,
            )
            if not ok:
                logger.error(
                    "Verifier LLM connectivity check FAILED — verification will fall back to heuristics. "
                    "Check AI__API_KEY, AI__BASE_URL, and AI__MODEL_VERIFIER settings."
                )

        logger.info("OpenSift engine initialized")

    async def shutdown(self) -> None:
        """Gracefully shut down all components."""
        await self.adapter_registry.shutdown_all()
        logger.info("OpenSift engine shut down")

    # ──────────────────────────────────────────────────────────────────────
    # Plan-only mode
    # ──────────────────────────────────────────────────────────────────────

    async def plan(self, request: SearchRequest) -> PlanResponse:
        """Execute only the query-planning stage (no search, no verification).

        Useful when you want to obtain the generated search queries and
        screening criteria without running the full filtering funnel.

        Args:
            request: The incoming search request.

        Returns:
            A PlanResponse with the generated criteria result and timing.
        """
        start_time = time.monotonic()
        request_id = f"plan_{uuid.uuid4().hex[:12]}"

        logger.info("Plan-only: Generating criteria for query: %s", request.query)
        criteria_result = await self.planner.plan(request)
        processing_time_ms = int((time.monotonic() - start_time) * 1000)

        logger.info(
            "Plan-only complete: %d search queries, %d criteria in %d ms",
            len(criteria_result.search_queries),
            len(criteria_result.criteria),
            processing_time_ms,
        )

        return PlanResponse(
            request_id=request_id,
            query=request.query,
            criteria_result=criteria_result,
            processing_time_ms=processing_time_ms,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Complete mode
    # ──────────────────────────────────────────────────────────────────────

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Execute the full search filtering funnel (complete mode).

        Waits for all results to be verified before returning.

        Args:
            request: The incoming search request.

        Returns:
            A SearchResponse with perfect, partial, and reject classifications.
        """
        start_time = time.monotonic()
        request_id = f"req_{uuid.uuid4().hex[:12]}"

        # ── Stage 1: Generate search queries + criteria ──
        logger.info("Stage 1: Generating criteria for query: %s", request.query)
        criteria_result = await self.planner.plan(request)
        logger.info(
            "Criteria generated: %d search queries, %d criteria",
            len(criteria_result.search_queries),
            len(criteria_result.criteria),
        )

        # ── Stage 2: Execute search queries via adapters ──
        logger.info("Stage 2: Executing %d search queries", len(criteria_result.search_queries))
        results = await self._execute_searches(criteria_result.search_queries, request)
        logger.info("Retrieved %d results", len(results))

        if not results:
            return SearchResponse(
                request_id=request_id,
                status="no_results",
                processing_time_ms=int((time.monotonic() - start_time) * 1000),
                query=request.query,
                criteria_result=criteria_result,
                total_scanned=0,
            )

        # ── Stage 3: Verify results against criteria ──
        question_lang = _detect_language(request.query)

        if request.options.verify:
            logger.info("Stage 3: Verifying %d results", len(results))
            validations = await self.verifier.verify_batch(
                results,
                criteria_result.criteria,
                request.query,
                question_lang=question_lang,
                max_concurrent=self.settings.search.max_concurrent_queries,
            )
        else:
            # Skip verification — return all as insufficient_information
            validations = [self.verifier._fallback_validation(criteria_result.criteria) for _ in results]

        # ── Stage 4: Classify results (or skip) ──
        if request.options.classify:
            logger.info("Stage 4: Classifying %d results", len(results))
            scored = ResultClassifier.classify_batch(results, validations, criteria_result.criteria)

            # Separate by classification
            perfect = [r for r in scored if r.classification == ResultClassification.PERFECT]
            partial = [r for r in scored if r.classification == ResultClassification.PARTIAL]
            rejected = [r for r in scored if r.classification == ResultClassification.REJECT]

            processing_time_ms = int((time.monotonic() - start_time) * 1000)

            logger.info(
                "Search complete: %d perfect, %d partial, %d rejected in %d ms",
                len(perfect),
                len(partial),
                len(rejected),
                processing_time_ms,
            )

            return SearchResponse(
                request_id=request_id,
                status="completed",
                processing_time_ms=processing_time_ms,
                query=request.query,
                criteria_result=criteria_result,
                perfect_results=perfect,
                partial_results=partial,
                rejected_results=rejected,
                rejected_count=len(rejected),
                total_scanned=len(results),
            )

        # ── classify=false: return raw verified results ──
        logger.info("Stage 4 skipped (classify=false): returning %d raw verified results", len(results))
        raw = [
            RawVerifiedResult(
                result=item.model_dump(),
                validation=validation,
            )
            for item, validation in zip(results, validations, strict=True)
        ]

        processing_time_ms = int((time.monotonic() - start_time) * 1000)

        return SearchResponse(
            request_id=request_id,
            status="completed",
            processing_time_ms=processing_time_ms,
            query=request.query,
            criteria_result=criteria_result,
            raw_results=raw,
            total_scanned=len(results),
        )

    # ──────────────────────────────────────────────────────────────────────
    # Streaming mode
    # ──────────────────────────────────────────────────────────────────────

    async def search_stream(self, request: SearchRequest) -> AsyncIterator[StreamEvent]:
        """Execute the search filtering funnel in streaming mode.

        Yields ``StreamEvent`` objects as results are verified one by one:

        1. ``event="criteria"``  — Planning complete, emitted once.
        2. ``event="result"``    — Emitted per result after verification + classification.
        3. ``event="done"``      — Final summary, emitted once at the end.
        4. ``event="error"``     — Emitted if an unrecoverable error occurs.

        Args:
            request: The incoming search request.

        Yields:
            StreamEvent instances.
        """
        start_time = time.monotonic()
        request_id = f"req_{uuid.uuid4().hex[:12]}"

        try:
            # ── Stage 1: Generate search queries + criteria ──
            logger.info("[stream] Stage 1: Generating criteria for query: %s", request.query)
            criteria_result = await self.planner.plan(request)

            yield StreamEvent(
                event="criteria",
                data={
                    "request_id": request_id,
                    "query": request.query,
                    "criteria_result": criteria_result.model_dump(),
                },
            )

            # ── Stage 2: Execute search queries via adapters ──
            logger.info("[stream] Stage 2: Executing %d search queries", len(criteria_result.search_queries))
            items = await self._execute_searches(criteria_result.search_queries, request)
            logger.info("[stream] Retrieved %d results", len(items))

            yield StreamEvent(
                event="search_complete",
                data={
                    "total_results": len(items),
                    "search_queries_count": len(criteria_result.search_queries),
                    "results": [item.model_dump() for item in items],
                },
            )

            if not items:
                yield StreamEvent(
                    event="done",
                    data={
                        "request_id": request_id,
                        "status": "no_results",
                        "total_scanned": 0,
                        "perfect_count": 0,
                        "partial_count": 0,
                        "rejected_count": 0,
                        "processing_time_ms": int((time.monotonic() - start_time) * 1000),
                    },
                )
                return

            # ── Stage 3 + 4: Verify (& optionally classify) one by one ──
            question_lang = _detect_language(request.query)
            criteria = criteria_result.criteria
            do_classify = request.options.classify

            perfect_count = 0
            partial_count = 0
            rejected_count = 0

            semaphore = asyncio.Semaphore(self.settings.search.max_concurrent_queries)

            async def _verify_item(item: ResultItem) -> tuple[ResultItem, ValidationResult]:
                async with semaphore:
                    if request.options.verify:
                        validation = await self.verifier.verify(
                            item,
                            criteria,
                            request.query,
                            question_lang,
                        )
                    else:
                        validation = self.verifier._fallback_validation(criteria)
                    return item, validation

            # Launch all verification tasks concurrently, yield as they complete
            pending = {asyncio.ensure_future(_verify_item(item)): i for i, item in enumerate(items)}

            for index, coro in enumerate(asyncio.as_completed(pending), start=1):
                item, validation = await coro

                if do_classify:
                    scored = ResultClassifier.classify(item, validation, criteria)

                    # Track counts
                    if scored.classification == ResultClassification.PERFECT:
                        perfect_count += 1
                    elif scored.classification == ResultClassification.PARTIAL:
                        partial_count += 1
                    else:
                        rejected_count += 1

                    yield StreamEvent(
                        event="result",
                        data={
                            "index": index,
                            "total": len(items),
                            "scored_result": scored.model_dump(),
                        },
                    )
                else:
                    raw = RawVerifiedResult(
                        result=item.model_dump(),
                        validation=validation,
                    )
                    yield StreamEvent(
                        event="result",
                        data={
                            "index": index,
                            "total": len(items),
                            "raw_result": raw.model_dump(),
                        },
                    )

            # ── Done ──
            processing_time_ms = int((time.monotonic() - start_time) * 1000)

            logger.info(
                "[stream] Search complete: %d perfect, %d partial, %d rejected in %d ms",
                perfect_count,
                partial_count,
                rejected_count,
                processing_time_ms,
            )

            yield StreamEvent(
                event="done",
                data={
                    "request_id": request_id,
                    "status": "completed",
                    "total_scanned": len(items),
                    "perfect_count": perfect_count,
                    "partial_count": partial_count,
                    "rejected_count": rejected_count,
                    "processing_time_ms": processing_time_ms,
                },
            )

        except Exception as e:
            logger.error("[stream] Search failed: %s", e, exc_info=True)
            yield StreamEvent(
                event="error",
                data={
                    "request_id": request_id,
                    "error": str(e),
                    "processing_time_ms": int((time.monotonic() - start_time) * 1000),
                },
            )

    # ──────────────────────────────────────────────────────────────────────
    # Batch mode
    # ──────────────────────────────────────────────────────────────────────

    async def batch_search(self, request: BatchSearchRequest) -> BatchSearchResponse:
        """Execute multiple search queries as a batch.

        Each query runs through the full filtering funnel independently.
        Results are assembled into a single ``BatchSearchResponse``.
        Optionally exports all results to CSV or JSON.

        Args:
            request: Batch search request with multiple queries.

        Returns:
            A BatchSearchResponse containing per-query results.
        """
        start_time = time.monotonic()

        # Run each query through the standard search pipeline
        tasks = [
            self.search(
                SearchRequest(
                    query=query,
                    options=request.options,
                    context=request.context,
                )
            )
            for query in request.queries
        ]

        raw_responses: list[SearchResponse | BaseException] = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[SearchResponse] = []
        for i, resp in enumerate(raw_responses):
            if isinstance(resp, BaseException):
                logger.warning("Batch query %d failed: %s", i, resp)
                results.append(
                    SearchResponse(
                        request_id=f"req_batch_{i}_error",
                        status="error",
                        processing_time_ms=0,
                        query=request.queries[i],
                        criteria_result={"search_queries": [], "criteria": []},  # type: ignore[arg-type]
                        total_scanned=0,
                    )
                )
            else:
                results.append(resp)

        processing_time_ms = int((time.monotonic() - start_time) * 1000)

        # Export if requested
        export_data: str | None = None
        if request.export_format:
            export_data = self._export_results(results, request.export_format)

        logger.info(
            "Batch search complete: %d queries in %d ms",
            len(request.queries),
            processing_time_ms,
        )

        return BatchSearchResponse(
            status="completed",
            processing_time_ms=processing_time_ms,
            total_queries=len(request.queries),
            results=results,
            export_format=request.export_format,
            export_data=export_data,
        )

    @staticmethod
    def _export_results(results: list[SearchResponse], fmt: str) -> str:
        """Export batch results to the requested format.

        Args:
            results: List of per-query search responses.
            fmt: Export format — ``"csv"`` or ``"json"``.

        Returns:
            Exported data as a string.
        """
        if fmt == "json":
            import json as json_mod

            rows = []
            for resp in results:
                for scored in [*resp.perfect_results, *resp.partial_results]:
                    rows.append(
                        {
                            "query": resp.query,
                            "classification": scored.classification.value,
                            "weighted_score": scored.weighted_score,
                            "title": scored.result.get("title", ""),
                            "content": scored.result.get("content", "")[:200],
                            "source_url": scored.result.get("source_url", ""),
                            "summary": scored.validation.summary,
                        }
                    )
            return json_mod.dumps(rows, ensure_ascii=False, indent=2)

        if fmt == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "query",
                    "classification",
                    "weighted_score",
                    "title",
                    "content_preview",
                    "source_url",
                    "summary",
                ]
            )
            for resp in results:
                for scored in [*resp.perfect_results, *resp.partial_results]:
                    writer.writerow(
                        [
                            resp.query,
                            scored.classification.value,
                            scored.weighted_score,
                            scored.result.get("title", ""),
                            scored.result.get("content", "")[:200],
                            scored.result.get("source_url", ""),
                            scored.validation.summary,
                        ]
                    )
            return output.getvalue()

        return ""

    # ──────────────────────────────────────────────────────────────────────
    # Shared internals
    # ──────────────────────────────────────────────────────────────────────

    async def _execute_searches(
        self,
        search_queries: list[str],
        request: SearchRequest,
    ) -> list[ResultItem]:
        """Execute search queries via adapters and return deduplicated results.

        Each search query is dispatched to every selected adapter (controlled by
        ``request.options.adapters``).  ``max_results`` applies **per query per
        adapter**, so the total results are the deduplicated union of all
        query x adapter combinations.

        If the adapter exposes a ``search_papers()`` method (e.g. AtomWalker),
        it is used directly to preserve full metadata, then converted to
        ``ResultItem``.  Otherwise, the standard ``search_and_normalize()``
        path is used.

        Args:
            search_queries: List of search query strings.
            request: The original search request (for options).

        Returns:
            Deduplicated list of ResultItem objects.
        """
        try:
            adapters = self.adapter_registry.get_adapters(request.options.adapters)
        except Exception:
            logger.warning("No search adapter available, returning empty results")
            return []

        tasks: list[asyncio.Task[Any]] = []
        task_meta: list[tuple[str, bool]] = []  # (adapter_name, use_paper_path)

        for adapter in adapters:
            use_paper_path = hasattr(adapter, "search_papers") and callable(adapter.search_papers)
            for query in search_queries:
                if use_paper_path:
                    tasks.append(
                        asyncio.ensure_future(
                            adapter.search_papers(query, request.options)  # type: ignore[attr-defined]
                        )
                    )
                else:
                    tasks.append(asyncio.ensure_future(adapter.search_and_normalize(query, request.options)))
                task_meta.append((adapter.name, use_paper_path))

        raw_results: list[Any] = await asyncio.gather(*tasks, return_exceptions=True)

        seen_titles: set[str] = set()
        items: list[ResultItem] = []

        for i, result in enumerate(raw_results):
            if isinstance(result, BaseException):
                adapter_name, _ = task_meta[i]
                logger.warning("Search query failed on adapter '%s': %s", adapter_name, result)
                continue
            adapter_name, use_paper_path = task_meta[i]
            for raw_item in result:
                item = raw_item.to_result_item() if use_paper_path else self._doc_to_result_item(raw_item)
                item.source_adapter = adapter_name

                key = item.title.strip().lower()
                if key not in seen_titles:
                    seen_titles.add(key)
                    items.append(item)

        return items

    @staticmethod
    def _doc_to_result_item(doc: object) -> ResultItem:
        """Convert a StandardDocument to a generic ResultItem.

        Maps the generic document schema to ResultItem.
        """
        title = getattr(doc, "title", "N/A")
        content = getattr(doc, "content", "N/A")
        metadata = getattr(doc, "metadata", None)

        url = getattr(metadata, "url", "N/A") if metadata else "N/A"
        source = getattr(metadata, "source", "N/A") if metadata else "N/A"
        author = getattr(metadata, "author", "N/A") if metadata else "N/A"
        published_date = ""
        if metadata and getattr(metadata, "published_date", None):
            published_date = str(metadata.published_date)
        tags = getattr(metadata, "tags", []) if metadata else []

        extra = getattr(metadata, "extra", {}) if metadata else {}

        fields: dict[str, str] = {}
        if author and author != "N/A":
            fields["author"] = author
        if source and source != "N/A":
            fields["source"] = source
        if published_date:
            fields["published_date"] = published_date
        if tags:
            fields["tags"] = "; ".join(tags)
        # Include any extra metadata from the adapter
        for k, v in extra.items():
            if v is not None and str(v) != "N/A":
                fields[k] = str(v)

        return ResultItem(
            title=title or "N/A",
            content=content or "N/A",
            source_url=url or "N/A",
            fields=fields,
        )
