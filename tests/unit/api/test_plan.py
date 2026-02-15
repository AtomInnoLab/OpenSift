"""Tests for the standalone plan endpoint POST /v1/plan."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from opensift.api.app import create_app
from opensift.api.deps import set_engine
from opensift.config.settings import Settings
from opensift.core.engine import OpenSiftEngine
from opensift.models.criteria import CriteriaResult, Criterion
from opensift.models.response import PlanResponse

# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_criteria_result() -> CriteriaResult:
    return CriteriaResult(
        search_queries=["solar nowcasting deep learning", '"solar irradiance" prediction'],
        criteria=[
            Criterion(
                criterion_id="c1",
                type="topic",
                name="Solar nowcasting",
                description="The paper addresses solar nowcasting or short-term prediction.",
                weight=0.6,
            ),
            Criterion(
                criterion_id="c2",
                type="method",
                name="Deep learning",
                description="The paper uses deep learning methods.",
                weight=0.4,
            ),
        ],
    )


def _mock_plan_response(query: str = "solar nowcasting") -> PlanResponse:
    return PlanResponse(
        request_id="plan_test123",
        query=query,
        criteria_result=_mock_criteria_result(),
        processing_time_ms=42,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def engine(settings: Settings) -> OpenSiftEngine:
    return OpenSiftEngine(settings)


@pytest.fixture
def client(settings: Settings, engine: OpenSiftEngine) -> TestClient:
    app = create_app(settings)
    set_engine(engine)
    yield TestClient(app)
    set_engine(None)


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/plan
# ══════════════════════════════════════════════════════════════════════════════


class TestPlan:
    """Tests for POST /v1/plan (standalone planning)."""

    def test_plan_returns_200(self, client: TestClient, engine: OpenSiftEngine) -> None:
        mock_resp = _mock_plan_response()
        with patch.object(engine, "plan", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post("/v1/plan", json={"query": "solar nowcasting"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["request_id"] == "plan_test123"
        assert body["query"] == "solar nowcasting"
        assert len(body["criteria_result"]["search_queries"]) == 2
        assert len(body["criteria_result"]["criteria"]) == 2
        assert body["processing_time_ms"] == 42

    def test_plan_criteria_have_correct_fields(self, client: TestClient, engine: OpenSiftEngine) -> None:
        mock_resp = _mock_plan_response()
        with patch.object(engine, "plan", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post("/v1/plan", json={"query": "solar nowcasting"})

        criteria = resp.json()["criteria_result"]["criteria"]
        for c in criteria:
            assert "criterion_id" in c
            assert "type" in c
            assert "name" in c
            assert "description" in c
            assert "weight" in c

    def test_plan_weights_sum_to_one(self, client: TestClient, engine: OpenSiftEngine) -> None:
        mock_resp = _mock_plan_response()
        with patch.object(engine, "plan", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post("/v1/plan", json={"query": "solar nowcasting"})

        criteria = resp.json()["criteria_result"]["criteria"]
        total = sum(c["weight"] for c in criteria)
        assert abs(total - 1.0) < 0.05

    def test_plan_with_decompose_false(self, client: TestClient, engine: OpenSiftEngine) -> None:
        """When decompose=false, planner returns simple fallback result."""
        mock_resp = PlanResponse(
            request_id="plan_simple",
            query="test",
            criteria_result=CriteriaResult(
                search_queries=["test"],
                criteria=[
                    Criterion(
                        criterion_id="criterion_1",
                        type="topic",
                        name="Query relevance",
                        description="The paper is directly relevant to: test",
                        weight=1.0,
                    ),
                ],
            ),
            processing_time_ms=2,
        )
        with patch.object(engine, "plan", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post(
                "/v1/plan",
                json={"query": "test", "options": {"decompose": False}},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["criteria_result"]["search_queries"] == ["test"]
        assert len(body["criteria_result"]["criteria"]) == 1

    def test_plan_empty_query_returns_422(self, client: TestClient) -> None:
        resp = client.post("/v1/plan", json={"query": ""})
        assert resp.status_code == 422

    def test_plan_missing_query_returns_422(self, client: TestClient) -> None:
        resp = client.post("/v1/plan", json={})
        assert resp.status_code == 422

    def test_plan_engine_error_returns_500(self, client: TestClient, engine: OpenSiftEngine) -> None:
        with patch.object(engine, "plan", new_callable=AsyncMock, side_effect=RuntimeError("LLM unavailable")):
            resp = client.post("/v1/plan", json={"query": "test query"})

        assert resp.status_code == 500
        assert "Plan processing failed" in resp.json()["detail"]

    def test_plan_preserves_query_text(self, client: TestClient, engine: OpenSiftEngine) -> None:
        query = "有哪些关于太阳能即时预报的深度学习论文？"
        mock_resp = _mock_plan_response(query=query)
        with patch.object(engine, "plan", new_callable=AsyncMock, return_value=mock_resp):
            resp = client.post("/v1/plan", json={"query": query})

        assert resp.status_code == 200
        assert resp.json()["query"] == query
