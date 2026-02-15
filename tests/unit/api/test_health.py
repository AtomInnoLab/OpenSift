"""Tests for the health check endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from opensift.api.app import create_app
from opensift.api.deps import set_engine
from opensift.config.settings import Settings
from opensift.core.engine import OpenSiftEngine


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Create a test client for the API."""
    app = create_app(settings)
    engine = OpenSiftEngine(settings)
    set_engine(engine)
    yield TestClient(app)
    set_engine(None)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "opensift"
        assert "version" in data

    def test_adapter_health_check(self, client: TestClient) -> None:
        response = client.get("/v1/health/adapters")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
