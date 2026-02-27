"""Search endpoint — AI-enhanced search with criteria generation, verification, and classification.

Supports two output modes:

- **Complete** (``stream=false``, default) — Standard JSON response after all
  results are verified.
- **Streaming** (``stream=true``) — Server-Sent Events (SSE) stream; results
  are emitted one by one as verification completes.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from opensift.api.deps import get_engine
from opensift.core.engine import OpenSiftEngine
from opensift.models.query import SearchRequest
from opensift.models.response import SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="AI-Enhanced Search",
    description=(
        "Execute an AI-enhanced search with automatic query decomposition, "
        "criteria generation, result verification, and classification.\n\n"
        "**Output modes:**\n"
        "- `stream: false` (default) — Returns a single JSON `SearchResponse` "
        "after all results are verified.\n"
        "- `stream: true` — Returns an SSE event stream (`text/event-stream`).\n\n"
        "**SSE event types (streaming mode):**\n"
        "| Event | Emitted | Description |\n"
        "|-------|---------|-------------|\n"
        "| `criteria` | once | Planning complete — contains `request_id`, `query`, `criteria_result` |\n"
        "| `search_complete` | once | Search finished — contains `total_results`, `search_queries_count`, and full `results` list |\n"
        "| `result` | per result | One result verified — contains `index`, `total`, and `scored_result` (classify=true) or `raw_result` (classify=false) |\n"
        "| `done` | once | All done — contains final counts (`perfect_count`, `partial_count`, `rejected_count`) and `processing_time_ms` |\n"
        "| `error` | 0–1 | Unrecoverable error — contains `error` message |"
    ),
    responses={
        200: {
            "description": "Complete JSON response (stream=false) or SSE stream (stream=true)",
            "content": {
                "application/json": {},
                "text/event-stream": {},
            },
        },
        422: {"description": "Validation error — invalid request body (missing query, bad options, etc.)"},
        500: {"description": "Internal server error — search processing failed"},
    },
)
async def search(
    request: SearchRequest,
    engine: OpenSiftEngine = Depends(get_engine),
) -> SearchResponse | StreamingResponse:
    """Execute an AI-enhanced search query.

    The full filtering funnel:
      1. Generates search queries + screening criteria from the user query
      2. Retrieves results via search adapters
      3. Validates each result against criteria using LLM
      4. Classifies results as perfect / partial / reject

    When ``stream=true``, returns an SSE stream where each verified result
    is emitted immediately (event type ``result``).

    Args:
        request: The search request with query, options, and context.
        engine: The OpenSift engine instance (injected).

    Returns:
        A SearchResponse (complete mode) or StreamingResponse (streaming mode).
    """
    if request.options.stream:
        return StreamingResponse(
            _sse_generator(engine, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Complete mode
    try:
        response = await engine.search(request)
        return response
    except Exception as e:
        logger.error("Search failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search processing failed: {e!s}",
        ) from e


async def _sse_generator(engine: OpenSiftEngine, request: SearchRequest) -> AsyncIterator[str]:
    """Async generator that yields SSE-formatted lines.

    Each event follows the SSE protocol::

        event: <event_type>
        data: <json_payload>

    """
    try:
        async for stream_event in engine.search_stream(request):
            event_type = stream_event.event
            payload = json.dumps(stream_event.data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"
    except Exception as e:
        logger.error("SSE stream error: %s", e, exc_info=True)
        error_payload = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"event: error\ndata: {error_payload}\n\n"
