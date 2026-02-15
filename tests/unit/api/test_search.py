"""Tests for the search (complete + stream) and batch search endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from opensift.api.app import create_app
from opensift.api.deps import set_engine
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
from opensift.models.response import BatchSearchResponse, RawVerifiedResult, SearchResponse, StreamEvent

# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_criteria_result() -> CriteriaResult:
    return CriteriaResult(
        search_queries=["test query"],
        criteria=[
            Criterion(
                criterion_id="c1",
                type="topic",
                name="Test",
                description="Test criterion.",
                weight=1.0,
            ),
        ],
    )


def _mock_scored_result(title: str = "Test Result") -> ScoredResult:
    return ScoredResult(
        result={"title": title, "content": "Test content", "source_url": "https://example.com"},
        validation=ValidationResult(
            criteria_assessment=[
                CriterionAssessment(
                    criterion_id="c1",
                    assessment=AssessmentType.SUPPORT,
                    explanation="Matches.",
                ),
            ],
            summary="Test summary.",
        ),
        classification=ResultClassification.PERFECT,
        weighted_score=1.0,
    )


def _mock_search_response(query: str = "test") -> SearchResponse:
    """Build a minimal SearchResponse for mocking."""
    return SearchResponse(
        request_id="req_test123",
        status="completed",
        processing_time_ms=100,
        query=query,
        criteria_result=_mock_criteria_result(),
        perfect_results=[_mock_scored_result()],
        partial_results=[],
        rejected_count=0,
        total_scanned=1,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def engine(settings: Settings) -> OpenSiftEngine:
    return OpenSiftEngine(settings)


@pytest.fixture
def client(settings: Settings, engine: OpenSiftEngine) -> TestClient:
    """Create a test client for the API."""
    app = create_app(settings)
    set_engine(engine)
    yield TestClient(app)
    set_engine(None)


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/search — Complete mode
# ══════════════════════════════════════════════════════════════════════════════


class TestSearchComplete:
    """Tests for POST /v1/search (complete mode, stream=false)."""

    def test_search_returns_200(self, client: TestClient, engine: OpenSiftEngine) -> None:
        with patch.object(engine, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = _mock_search_response("solar nowcasting")

            resp = client.post(
                "/v1/search",
                json={"query": "solar nowcasting", "options": {"max_results": 5}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["query"] == "solar nowcasting"
        assert len(data["perfect_results"]) == 1
        assert data["perfect_results"][0]["classification"] == "perfect"

    def test_search_missing_query_returns_422(self, client: TestClient) -> None:
        resp = client.post("/v1/search", json={"options": {}})
        assert resp.status_code == 422

    def test_search_empty_query_returns_422(self, client: TestClient) -> None:
        resp = client.post("/v1/search", json={"query": ""})
        assert resp.status_code == 422

    def test_search_engine_error_returns_500(self, client: TestClient, engine: OpenSiftEngine) -> None:
        with patch.object(engine, "search", new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = RuntimeError("LLM unavailable")

            resp = client.post("/v1/search", json={"query": "test"})

        assert resp.status_code == 500
        assert "LLM unavailable" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/search — Streaming mode
# ══════════════════════════════════════════════════════════════════════════════


class TestSearchStream:
    """Tests for POST /v1/search with stream=true (SSE mode)."""

    def test_stream_returns_sse_content_type(self, client: TestClient, engine: OpenSiftEngine) -> None:
        async def _mock_stream(_request):
            yield StreamEvent(event="criteria", data={"request_id": "req_test", "query": "test", "criteria_result": {}})
            yield StreamEvent(event="done", data={"request_id": "req_test", "status": "completed", "total_scanned": 0, "perfect_count": 0, "partial_count": 0, "rejected_count": 0, "processing_time_ms": 50})

        with patch.object(engine, "search_stream", side_effect=_mock_stream):
            resp = client.post(
                "/v1/search",
                json={"query": "test", "options": {"stream": True}},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        body = resp.text
        assert "event: criteria" in body
        assert "event: done" in body

    def test_stream_contains_result_events(self, client: TestClient, engine: OpenSiftEngine) -> None:
        scored = _mock_scored_result()

        async def _mock_stream(_request):
            yield StreamEvent(event="criteria", data={"request_id": "req_s", "query": "q", "criteria_result": _mock_criteria_result().model_dump()})
            yield StreamEvent(event="result", data={"index": 1, "total": 1, "scored_result": scored.model_dump()})
            yield StreamEvent(event="done", data={"request_id": "req_s", "status": "completed", "total_scanned": 1, "perfect_count": 1, "partial_count": 0, "rejected_count": 0, "processing_time_ms": 100})

        with patch.object(engine, "search_stream", side_effect=_mock_stream):
            resp = client.post(
                "/v1/search",
                json={"query": "q", "options": {"stream": True}},
            )

        body = resp.text
        assert "event: result" in body
        assert "Test Result" in body

    def test_stream_error_event(self, client: TestClient, engine: OpenSiftEngine) -> None:
        async def _mock_stream(_request):
            yield StreamEvent(event="error", data={"request_id": "req_err", "error": "Something broke"})

        with patch.object(engine, "search_stream", side_effect=_mock_stream):
            resp = client.post(
                "/v1/search",
                json={"query": "test", "options": {"stream": True}},
            )

        assert "event: error" in resp.text
        assert "Something broke" in resp.text


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/search/batch
# ══════════════════════════════════════════════════════════════════════════════


class TestBatchSearch:
    """Tests for POST /v1/search/batch."""

    def test_batch_returns_200(self, client: TestClient, engine: OpenSiftEngine) -> None:
        mock_batch = BatchSearchResponse(
            status="completed",
            processing_time_ms=500,
            total_queries=2,
            results=[_mock_search_response("query 1"), _mock_search_response("query 2")],
        )

        with patch.object(engine, "batch_search", new_callable=AsyncMock) as mock:
            mock.return_value = mock_batch

            resp = client.post(
                "/v1/search/batch",
                json={"queries": ["query 1", "query 2"], "options": {"max_results": 5}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["total_queries"] == 2
        assert len(data["results"]) == 2

    def test_batch_with_export_csv(self, client: TestClient, engine: OpenSiftEngine) -> None:
        mock_batch = BatchSearchResponse(
            status="completed",
            processing_time_ms=500,
            total_queries=1,
            results=[_mock_search_response("test")],
            export_format="csv",
            export_data="query,classification,weighted_score,title\ntest,perfect,1.0,Test Result\n",
        )

        with patch.object(engine, "batch_search", new_callable=AsyncMock) as mock:
            mock.return_value = mock_batch

            resp = client.post(
                "/v1/search/batch",
                json={"queries": ["test"], "export_format": "csv"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["export_format"] == "csv"
        assert "Test Result" in data["export_data"]

    def test_batch_empty_queries_returns_422(self, client: TestClient) -> None:
        resp = client.post("/v1/search/batch", json={"queries": []})
        assert resp.status_code == 422

    def test_batch_engine_error_returns_500(self, client: TestClient, engine: OpenSiftEngine) -> None:
        with patch.object(engine, "batch_search", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("Batch failed")

            resp = client.post(
                "/v1/search/batch",
                json={"queries": ["test"]},
            )

        assert resp.status_code == 500
        assert "Batch failed" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/search — classify=false (raw verification output)
# ══════════════════════════════════════════════════════════════════════════════


def _mock_raw_validation() -> ValidationResult:
    return ValidationResult(
        criteria_assessment=[
            CriterionAssessment(
                criterion_id="c1",
                assessment=AssessmentType.SUPPORT,
                explanation="Matches criterion.",
            ),
        ],
        summary="Test summary.",
    )


def _mock_raw_search_response(query: str = "test") -> SearchResponse:
    """Build a SearchResponse with raw_results (classify=false)."""
    return SearchResponse(
        request_id="req_raw_test",
        status="completed",
        processing_time_ms=80,
        query=query,
        criteria_result=_mock_criteria_result(),
        raw_results=[
            RawVerifiedResult(
                result={"title": "Raw Test", "content": "Raw content"},
                validation=_mock_raw_validation(),
            ),
        ],
        total_scanned=1,
    )


class TestSearchClassifyFalse:
    """Tests for POST /v1/search with classify=false (skip classifier)."""

    def test_classify_false_returns_raw_results(self, client: TestClient, engine: OpenSiftEngine) -> None:
        mock_resp = _mock_raw_search_response("solar nowcasting")
        with patch.object(engine, "search", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post(
                "/v1/search",
                json={"query": "solar nowcasting", "options": {"classify": False}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert len(data["raw_results"]) == 1
        assert data["raw_results"][0]["result"]["title"] == "Raw Test"
        assert data["raw_results"][0]["validation"]["summary"] == "Test summary."
        # Classified fields should be empty
        assert data["perfect_results"] == []
        assert data["partial_results"] == []
        assert data["rejected_count"] == 0

    def test_classify_false_raw_result_has_validation(self, client: TestClient, engine: OpenSiftEngine) -> None:
        mock_resp = _mock_raw_search_response()
        with patch.object(engine, "search", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post(
                "/v1/search",
                json={"query": "test", "options": {"classify": False}},
            )

        raw = resp.json()["raw_results"][0]
        assert "validation" in raw
        assert "criteria_assessment" in raw["validation"]
        assert raw["validation"]["criteria_assessment"][0]["assessment"] == "support"
        assert "classification" not in raw  # no classification field
        assert "weighted_score" not in raw  # no score field

    def test_classify_false_stream_returns_raw_result_events(self, client: TestClient, engine: OpenSiftEngine) -> None:
        raw = RawVerifiedResult(
            result={"title": "Stream Raw", "content": "Content"},
            validation=_mock_raw_validation(),
        )

        async def _mock_stream(_request):
            yield StreamEvent(event="criteria", data={"request_id": "req_r", "query": "q", "criteria_result": _mock_criteria_result().model_dump()})
            yield StreamEvent(event="result", data={"index": 1, "total": 1, "raw_result": raw.model_dump()})
            yield StreamEvent(event="done", data={"request_id": "req_r", "status": "completed", "total_scanned": 1, "perfect_count": 0, "partial_count": 0, "rejected_count": 0, "processing_time_ms": 50})

        with patch.object(engine, "search_stream", side_effect=_mock_stream):
            resp = client.post(
                "/v1/search",
                json={"query": "q", "options": {"stream": True, "classify": False}},
            )

        body = resp.text
        assert "event: result" in body
        assert "raw_result" in body
        assert "Stream Raw" in body

    def test_classify_true_is_default(self, client: TestClient, engine: OpenSiftEngine) -> None:
        """Default classify=true returns classified results, not raw."""
        mock_resp = _mock_search_response("test")
        with patch.object(engine, "search", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post("/v1/search", json={"query": "test"})

        data = resp.json()
        assert len(data["perfect_results"]) == 1
        assert data["raw_results"] == []
