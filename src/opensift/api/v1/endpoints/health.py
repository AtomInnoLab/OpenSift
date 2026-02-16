"""Health check endpoints — System and adapter health monitoring."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from opensift import __version__
from opensift.api.deps import get_engine
from opensift.core.engine import OpenSiftEngine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    summary="System Health Check",
    description="Check overall system health status, including active adapter info.",
)
async def health_check(
    engine: OpenSiftEngine = Depends(get_engine),
) -> dict:
    """Basic health check endpoint with adapter info."""
    return {
        "status": "healthy",
        "version": __version__,
        "service": "opensift",
        "default_adapter": engine.settings.search.default_adapter,
        "active_adapters": engine.adapter_registry.active_adapters,
    }


@router.get(
    "/health/adapters",
    summary="Adapter Health Check",
    description="Check the health status of all configured search adapters.",
)
async def adapter_health(
    engine: OpenSiftEngine = Depends(get_engine),
) -> dict:
    """Check health of all search adapters.

    Returns health status, latency, and error rates for each adapter.
    """
    adapter_statuses = await engine.adapter_registry.health_check_all()
    return {name: status.model_dump() for name, status in adapter_statuses.items()}
