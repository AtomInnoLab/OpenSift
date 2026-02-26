"""Query Planner — Generates search queries and screening criteria from user queries.

The planner is the first stage of the OpenSift filtering funnel. It uses an LLM
to analyze the user's natural language query and produce:
  1. search_queries: 2-4 search queries for paper retrieval
  2. criteria: 1-4 screening criteria for result validation

Supports fallback to heuristic decomposition when the LLM is unavailable.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from opensift.core.llm.client import LLMClient, LLMError
from opensift.core.llm.prompts import CRITERIA_SYSTEM_PROMPT, CRITERIA_USER_PROMPT
from opensift.models.criteria import CriteriaResult, Criterion

if TYPE_CHECKING:
    from opensift.config.settings import Settings
    from opensift.models.query import SearchRequest

logger = logging.getLogger(__name__)


class QueryPlanner:
    """Generates search queries and screening criteria from user queries.

    The planner analyzes user intent via LLM and produces a CriteriaResult
    containing search_queries for retrieval and criteria for filtering.

    When the LLM is unavailable or fails, falls back to heuristic-based
    decomposition that uses the original query directly.

    Attributes:
        settings: Application configuration.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm_client: LLMClient | None = None

        # Initialize LLM client if API key is configured
        if settings.ai.api_key and settings.ai.api_key not in ("", "test-key"):
            self._llm_client = LLMClient(settings.ai)
            logger.info("Planner LLM client initialized (model=%s)", settings.ai.model_planner)
        else:
            logger.warning("Planner LLM client NOT initialized (no API key) — using heuristic fallback")

    async def plan(self, request: SearchRequest) -> CriteriaResult:
        """Generate search queries and criteria for the given request.

        Args:
            request: The incoming search request.

        Returns:
            A CriteriaResult with search_queries and criteria.
        """
        start_time = time.monotonic()

        # Skip LLM if decomposition is disabled
        if not request.options.decompose:
            return self._create_simple_result(request.query)

        # Try LLM-based criteria generation
        if self._llm_client:
            try:
                logger.info(
                    "Planner calling LLM: query=%r, model=%s, base_url=%s",
                    request.query[:120],
                    self.settings.ai.model_planner,
                    self.settings.ai.base_url,
                )
                result = await self._generate_with_llm(request.query)
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "Criteria generated via LLM in %d ms: %d search_queries, %d criteria",
                    elapsed_ms,
                    len(result.search_queries),
                    len(result.criteria),
                )
                return result
            except (LLMError, Exception) as exc:
                logger.warning(
                    "LLM criteria generation failed (model=%s, url=%s): %s — falling back to heuristic",
                    self.settings.ai.model_planner,
                    self.settings.ai.base_url,
                    exc,
                    exc_info=True,
                )

        return self._create_simple_result(request.query)

    async def _generate_with_llm(self, query: str) -> CriteriaResult:
        """Use an LLM to generate search queries and criteria.

        Args:
            query: The user's natural language query.

        Returns:
            Parsed CriteriaResult from LLM output.

        Raises:
            LLMError: If the LLM call or parsing fails.
        """
        assert self._llm_client is not None

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        user_prompt = CRITERIA_USER_PROMPT.format(
            current_time=current_time,
            query=query,
        )

        raw = await self._llm_client.chat_json(
            system_prompt=CRITERIA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=self.settings.ai.model_planner,
            temperature=0.6,
        )

        return self._parse_criteria_response(raw)

    def _parse_criteria_response(self, raw: dict) -> CriteriaResult:
        """Parse and validate the raw LLM response into a CriteriaResult.

        Args:
            raw: Raw JSON dict from the LLM.

        Returns:
            Validated CriteriaResult.

        Raises:
            LLMError: If the response structure is invalid.
        """
        search_queries = raw.get("search_queries")
        criteria_raw = raw.get("criteria")

        if not search_queries or not isinstance(search_queries, list):
            raise LLMError("LLM response missing or invalid 'search_queries'")
        if not criteria_raw or not isinstance(criteria_raw, list):
            raise LLMError("LLM response missing or invalid 'criteria'")

        # Parse criteria with auto-generated IDs
        criteria: list[Criterion] = []
        for i, c in enumerate(criteria_raw, start=1):
            criteria.append(
                Criterion(
                    criterion_id=c.get("criterion_id", f"criterion_{i}"),
                    type=c.get("type", "topic"),
                    name=c.get("name", f"Criterion {i}"),
                    description=c.get("description", ""),
                    weight=float(c.get("weight", 0.0)),
                )
            )

        # Validate weights sum to ~1.0
        total_weight = sum(c.weight for c in criteria)
        if abs(total_weight - 1.0) > 0.05:
            logger.warning("Criteria weights sum to %.2f (expected 1.0), normalizing", total_weight)
            if total_weight > 0:
                for c in criteria:
                    c.weight = round(c.weight / total_weight, 2)
                # Fix rounding to ensure exact 1.0
                diff = 1.0 - sum(c.weight for c in criteria)
                criteria[-1].weight = round(criteria[-1].weight + diff, 2)

        return CriteriaResult(
            search_queries=search_queries,
            criteria=criteria,
        )

    @staticmethod
    def _create_simple_result(query: str) -> CriteriaResult:
        """Create a simple fallback result using the original query.

        Used when LLM is unavailable or decomposition is disabled.
        Generates at least 2 query variations to improve recall.
        """
        queries = [query]

        tokens = query.split()
        if len(tokens) >= 4:
            mid = len(tokens) // 2
            queries.append(" ".join(tokens[:mid]))
            queries.append(" ".join(tokens[mid:]))
        elif len(tokens) >= 2:
            queries.append(" ".join(tokens[::-1]))
        else:
            queries.append(f"{query} overview")

        seen: set[str] = set()
        unique: list[str] = []
        for q in queries:
            key = q.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(q.strip())
        queries = unique or [query]

        return CriteriaResult(
            search_queries=queries,
            criteria=[
                Criterion(
                    criterion_id="criterion_1",
                    type="topic",
                    name="Query relevance",
                    description=f"The result is directly relevant to: {query}",
                    weight=1.0,
                ),
            ],
        )
