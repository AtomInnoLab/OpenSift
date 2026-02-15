"""Plan endpoint — Standalone query planning (criteria generation) without search/verification.

Exposes the Planner as an independent capability, allowing clients to:
  1. Generate search queries from a natural language query
  2. Generate screening criteria with weights
  3. Use the output for downstream tooling, custom pipelines, or inspection
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from opensift.api.deps import get_engine
from opensift.core.engine import OpenSiftEngine
from opensift.models.query import SearchRequest
from opensift.models.response import PlanResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Standalone Query Planning",
    description=(
        "Execute the query-planning stage only — generate search queries and "
        "screening criteria from a natural language query.\n\n"
        "This endpoint does **not** run the search or verification stages. "
        "It is useful for:\n"
        "- Inspecting and debugging what the planner produces\n"
        "- Feeding generated queries into your own search pipeline\n"
        "- Pre-computing criteria for batch or incremental workflows"
    ),
)
async def plan(
    request: SearchRequest,
    engine: OpenSiftEngine = Depends(get_engine),
) -> PlanResponse:
    """Generate search queries and screening criteria from a user query.

    Runs only the Planner (LLM-based or heuristic fallback), skipping
    the search adapter and verifier stages entirely.

    Args:
        request: The search request with query, options, and context.
        engine: The OpenSift engine instance (injected).

    Returns:
        A PlanResponse with the generated criteria result and timing.
    """
    try:
        return await engine.plan(request)
    except Exception as e:
        logger.error("Plan failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Plan processing failed: {e!s}",
        ) from e
