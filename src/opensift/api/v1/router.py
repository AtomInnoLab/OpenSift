"""API v1 Router — Core search, plan, batch, and health endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from opensift.api.v1.endpoints.batch import router as batch_router
from opensift.api.v1.endpoints.health import router as health_router
from opensift.api.v1.endpoints.plan import router as plan_router
from opensift.api.v1.endpoints.search import router as search_router

router = APIRouter(tags=["v1"])
router.include_router(search_router)
router.include_router(plan_router)
router.include_router(batch_router)
router.include_router(health_router)
