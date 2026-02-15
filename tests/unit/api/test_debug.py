"""Tests for the debug panel endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from opensift.api.app import create_app
from opensift.api.deps import set_engine
from opensift.config.settings import Settings
from opensift.core.engine import OpenSiftEngine


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    engine = OpenSiftEngine(settings)
    set_engine(engine)
    yield TestClient(app)
    set_engine(None)


class TestDebugPanel:
    """Tests for GET /debug."""

    def test_debug_returns_html(self, client: TestClient) -> None:
        resp = client.get("/debug")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_debug_contains_opensift_title(self, client: TestClient) -> None:
        resp = client.get("/debug")
        assert "OpenSift" in resp.text
        assert "Debug Panel" in resp.text

    def test_debug_contains_search_elements(self, client: TestClient) -> None:
        resp = client.get("/debug")
        assert "searchQuery" in resp.text
        assert "streamQuery" in resp.text
        assert "batchQueries" in resp.text
