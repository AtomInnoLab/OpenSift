"""Tests for the OpenSift Python SDK client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from opensift.api.app import create_app
from opensift.api.deps import set_engine
from opensift.client.client import AsyncOpenSiftClient, _parse_sse_stream
from opensift.config.settings import Settings
from opensift.core.engine import OpenSiftEngine
from opensift.models.assessment import (
    AssessmentType,
    CriterionAssessment,
    ResultClassification,
    ScoredResult,
    ValidationResult,
)
from opensift.models.criteria import CriteriaResult, Criterion
from opensift.models.response import BatchSearchResponse, PlanResponse, SearchResponse, StreamEvent

# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_search_response(query: str = "test") -> SearchResponse:
    return SearchResponse(
        request_id="req_sdk_test",
        status="completed",
        processing_time_ms=42,
        query=query,
        criteria_result=CriteriaResult(
            search_queries=["q"],
            criteria=[
                Criterion(
                    criterion_id="c1",
                    type="topic",
                    name="T",
                    description="D",
                    weight=1.0,
                ),
            ],
        ),
        perfect_results=[
            ScoredResult(
                result={"title": "SDK Test", "content": "Hello"},
                validation=ValidationResult(
                    criteria_assessment=[
                        CriterionAssessment(
                            criterion_id="c1",
                            assessment=AssessmentType.SUPPORT,
                            explanation="OK",
                        ),
                    ],
                    summary="OK summary.",
                ),
                classification=ResultClassification.PERFECT,
                weighted_score=1.0,
            ),
        ],
        partial_results=[],
        rejected_count=0,
        total_scanned=1,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def engine(settings: Settings) -> OpenSiftEngine:
    return OpenSiftEngine(settings)


@pytest.fixture
def app_client(settings: Settings, engine: OpenSiftEngine) -> TestClient:
    """TestClient that acts as a live server for the SDK."""
    app = create_app(settings)
    set_engine(engine)
    yield TestClient(app)
    set_engine(None)


# ══════════════════════════════════════════════════════════════════════════════
# AsyncOpenSiftClient tests
# ══════════════════════════════════════════════════════════════════════════════


class TestAsyncOpenSiftClient:
    """Test the async SDK client via a real FastAPI TestClient."""

    async def test_health(self, app_client: TestClient) -> None:
        """SDK health check should return status='healthy'."""
        # Use httpx transport from TestClient for in-process testing
        import httpx

        transport = httpx.ASGITransport(app=app_client.app)
        async with AsyncOpenSiftClient(base_url="http://testserver", transport=transport) as sdk:
            result = await sdk.health()

        assert result["status"] == "healthy"
        assert result["service"] == "opensift"

    async def test_search_complete(self, app_client: TestClient, engine: OpenSiftEngine) -> None:
        """SDK search (complete mode) returns expected data."""
        import httpx

        transport = httpx.ASGITransport(app=app_client.app)

        with patch.object(engine, "search", new_callable=AsyncMock) as mock:
            mock.return_value = _mock_search_response("sdk query")

            async with AsyncOpenSiftClient(base_url="http://testserver", transport=transport) as sdk:
                result = await sdk.search("sdk query", max_results=5)

        assert result["status"] == "completed"
        assert result["query"] == "sdk query"
        assert len(result["perfect_results"]) == 1

    async def test_search_stream(self, app_client: TestClient, engine: OpenSiftEngine) -> None:
        """SDK search_stream yields SSE events."""
        import httpx

        transport = httpx.ASGITransport(app=app_client.app)

        async def _mock_stream(_request):
            yield StreamEvent(event="criteria", data={"request_id": "req", "query": "q", "criteria_result": {}})
            yield StreamEvent(event="done", data={"request_id": "req", "status": "completed", "total_scanned": 0, "perfect_count": 0, "partial_count": 0, "rejected_count": 0, "processing_time_ms": 1})

        with patch.object(engine, "search_stream", side_effect=_mock_stream):
            events: list[dict] = []
            async with AsyncOpenSiftClient(base_url="http://testserver", transport=transport) as sdk:
                async for ev in sdk.search_stream("q"):
                    events.append(ev)

        assert len(events) == 2
        assert events[0]["event"] == "criteria"
        assert events[1]["event"] == "done"

    async def test_plan(self, app_client: TestClient, engine: OpenSiftEngine) -> None:
        """SDK plan returns search queries and criteria."""
        import httpx

        transport = httpx.ASGITransport(app=app_client.app)
        mock_plan = PlanResponse(
            request_id="plan_sdk_test",
            query="solar nowcasting",
            criteria_result=CriteriaResult(
                search_queries=["solar nowcasting", '"solar irradiance" prediction'],
                criteria=[
                    Criterion(
                        criterion_id="c1",
                        type="topic",
                        name="Solar nowcasting",
                        description="Paper addresses solar nowcasting.",
                        weight=0.6,
                    ),
                    Criterion(
                        criterion_id="c2",
                        type="method",
                        name="Deep learning",
                        description="Paper uses deep learning.",
                        weight=0.4,
                    ),
                ],
            ),
            processing_time_ms=30,
        )

        with patch.object(engine, "plan", new_callable=AsyncMock) as mock:
            mock.return_value = mock_plan

            async with AsyncOpenSiftClient(base_url="http://testserver", transport=transport) as sdk:
                result = await sdk.plan("solar nowcasting")

        assert result["request_id"] == "plan_sdk_test"
        assert result["query"] == "solar nowcasting"
        assert len(result["criteria_result"]["search_queries"]) == 2
        assert len(result["criteria_result"]["criteria"]) == 2
        assert result["processing_time_ms"] == 30

    async def test_batch_search(self, app_client: TestClient, engine: OpenSiftEngine) -> None:
        """SDK batch_search returns results for multiple queries."""
        import httpx

        transport = httpx.ASGITransport(app=app_client.app)
        mock_batch = BatchSearchResponse(
            status="completed",
            processing_time_ms=100,
            total_queries=2,
            results=[_mock_search_response("q1"), _mock_search_response("q2")],
        )

        with patch.object(engine, "batch_search", new_callable=AsyncMock) as mock:
            mock.return_value = mock_batch

            async with AsyncOpenSiftClient(base_url="http://testserver", transport=transport) as sdk:
                result = await sdk.batch_search(["q1", "q2"])

        assert result["total_queries"] == 2
        assert len(result["results"]) == 2


# ══════════════════════════════════════════════════════════════════════════════
# SSE parser tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSSEParser:
    """Tests for the internal _parse_sse_stream utility."""

    async def test_parse_valid_sse(self) -> None:
        """Parser correctly separates SSE events."""

        class FakeResponse:
            """Fake httpx.Response with aiter_lines."""

            async def aiter_lines(self):
                lines = [
                    "event: criteria",
                    'data: {"query": "test"}',
                    "",
                    "event: done",
                    'data: {"status": "ok"}',
                    "",
                ]
                for line in lines:
                    yield line

        events = [ev async for ev in _parse_sse_stream(FakeResponse())]  # type: ignore[arg-type]

        assert len(events) == 2
        assert events[0]["event"] == "criteria"
        assert events[0]["data"]["query"] == "test"
        assert events[1]["event"] == "done"

    async def test_parse_invalid_json_fallback(self) -> None:
        """Parser returns raw data if JSON is invalid."""

        class FakeResponse:
            async def aiter_lines(self):
                lines = [
                    "event: error",
                    "data: not-json-at-all",
                    "",
                ]
                for line in lines:
                    yield line

        events = [ev async for ev in _parse_sse_stream(FakeResponse())]  # type: ignore[arg-type]

        assert len(events) == 1
        assert events[0]["event"] == "error"
        assert events[0]["data"]["raw"] == "not-json-at-all"
