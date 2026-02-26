"""Batch search endpoint — Execute multiple search queries in one request."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from opensift.api.deps import get_engine
from opensift.core.engine import OpenSiftEngine
from opensift.models.query import BatchSearchRequest
from opensift.models.response import BatchSearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/search/batch",
    response_model=BatchSearchResponse,
    summary="Batch AI-Enhanced Search",
    description=(
        "Execute multiple search queries in a single request. Each query "
        "goes through the full filtering funnel (planning → search → "
        "verification → classification). Optionally export results to "
        "CSV or JSON format.\n\n"
        "Supports up to 20 queries per batch. Each query runs independently; "
        "a failure in one query does not affect others."
    ),
    responses={
        422: {"description": "Validation error — invalid request body (empty queries, bad options, etc.)"},
        500: {"description": "Internal server error — batch processing failed"},
    },
)
async def batch_search(
    request: BatchSearchRequest,
    engine: OpenSiftEngine = Depends(get_engine),
) -> BatchSearchResponse:
    """Execute a batch of search queries.

    Args:
        request: Batch search request with multiple queries and shared options.
        engine: The OpenSift engine instance (injected).

    Returns:
        A BatchSearchResponse with per-query results and optional export data.
    """
    try:
        response = await engine.batch_search(request)
        return response
    except Exception as e:
        logger.error("Batch search failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch search processing failed: {e!s}",
        ) from e
