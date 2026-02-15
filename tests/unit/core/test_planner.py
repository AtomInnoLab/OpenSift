"""Tests for the Query Planner (criteria generation)."""

from __future__ import annotations

import pytest

from opensift.config.settings import Settings
from opensift.core.planner.planner import QueryPlanner
from opensift.models.criteria import CriteriaResult
from opensift.models.query import SearchOptions, SearchRequest


class TestQueryPlanner:
    """Tests for QueryPlanner."""

    @pytest.fixture
    def planner(self, settings: Settings) -> QueryPlanner:
        return QueryPlanner(settings)

    @pytest.mark.asyncio
    async def test_simple_plan_no_decomposition(self, planner: QueryPlanner) -> None:
        """When decompose=False, returns the original query as-is."""
        request = SearchRequest(
            query="solar nowcasting",
            options=SearchOptions(decompose=False),
        )
        result = await planner.plan(request)
        assert isinstance(result, CriteriaResult)
        assert len(result.search_queries) == 1
        assert result.search_queries[0] == "solar nowcasting"
        assert len(result.criteria) == 1
        assert result.criteria[0].weight == 1.0

    @pytest.mark.asyncio
    async def test_fallback_when_no_llm(self, planner: QueryPlanner) -> None:
        """Without LLM, should fall back to simple result."""
        request = SearchRequest(query="有哪些关于太阳能即时预报的论文？")
        result = await planner.plan(request)
        assert isinstance(result, CriteriaResult)
        assert len(result.search_queries) >= 1
        assert len(result.criteria) >= 1
        # All weights should sum to 1.0
        total_weight = sum(c.weight for c in result.criteria)
        assert abs(total_weight - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_criteria_ids_are_set(self, planner: QueryPlanner) -> None:
        """Criteria should have proper IDs."""
        request = SearchRequest(query="machine learning for drug discovery")
        result = await planner.plan(request)
        for criterion in result.criteria:
            assert criterion.criterion_id.startswith("criterion_")

    def test_parse_criteria_response(self, planner: QueryPlanner) -> None:
        """Test parsing a typical LLM response."""
        raw = {
            "search_queries": [
                '"solar nowcasting"',
                '"solar" AND "nowcasting"',
                "solar nowcasting",
            ],
            "criteria": [
                {
                    "type": "task",
                    "name": "Solar nowcasting focus",
                    "description": "The paper addresses solar nowcasting methods.",
                    "weight": 1.0,
                }
            ],
        }
        result = planner._parse_criteria_response(raw)
        assert len(result.search_queries) == 3
        assert len(result.criteria) == 1
        assert result.criteria[0].criterion_id == "criterion_1"
        assert result.criteria[0].type == "task"
        assert result.criteria[0].weight == 1.0

    def test_parse_criteria_normalizes_weights(self, planner: QueryPlanner) -> None:
        """Weights that don't sum to 1.0 should be normalized."""
        raw = {
            "search_queries": ["test"],
            "criteria": [
                {"type": "topic", "name": "A", "description": "Desc A", "weight": 0.3},
                {"type": "method", "name": "B", "description": "Desc B", "weight": 0.3},
            ],
        }
        result = planner._parse_criteria_response(raw)
        total = sum(c.weight for c in result.criteria)
        assert abs(total - 1.0) < 0.01

    def test_create_simple_result(self) -> None:
        """Test the fallback simple result."""
        result = QueryPlanner._create_simple_result("test query")
        assert result.search_queries == ["test query"]
        assert len(result.criteria) == 1
        assert result.criteria[0].weight == 1.0
