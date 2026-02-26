"""Health check endpoints — System and adapter health monitoring."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from opensift import __version__
from opensift.adapters.base.adapter import AdapterHealth
from opensift.api.deps import get_engine
from opensift.core.engine import OpenSiftEngine

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Response models ──────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """System health check response."""

    status: str = Field(description="Health status (e.g. 'healthy')")
    version: str = Field(description="OpenSift server version")
    service: str = Field(description="Service name ('opensift')")
    default_adapter: str = Field(description="Name of the default search adapter")
    active_adapters: list[str] = Field(description="List of currently active adapter names")


class AdapterHealthResponse(BaseModel):
    """Per-adapter health check response.

    Keys are adapter names, values are ``AdapterHealth`` objects with
    status, latency, error rate, and optional message.
    """

    adapters: dict[str, AdapterHealth] = Field(
        description="Map of adapter name to its health status",
    )


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Check",
    description=(
        "Returns overall system health, server version, and a list of "
        "currently active search adapters with the default adapter name."
    ),
)
async def health_check(
    engine: OpenSiftEngine = Depends(get_engine),
) -> HealthResponse:
    """Basic health check endpoint with adapter info."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        service="opensift",
        default_adapter=engine.settings.search.default_adapter,
        active_adapters=engine.adapter_registry.active_adapters,
    )


@router.get(
    "/health/adapters",
    response_model=AdapterHealthResponse,
    summary="Adapter Health Check",
    description=(
        "Run health checks on every active search adapter and return "
        "per-adapter status including latency, error rate, and diagnostic message."
    ),
)
async def adapter_health(
    engine: OpenSiftEngine = Depends(get_engine),
) -> AdapterHealthResponse:
    """Check health of all search adapters."""
    adapter_statuses = await engine.adapter_registry.health_check_all()
    return AdapterHealthResponse(adapters=adapter_statuses)
