"""Search response models — Structured output of the OpenSift filtering funnel.

Supports two output modes:

1. **Complete mode** (``stream=false``) — Returns a single ``SearchResponse``
   JSON body after all results are verified and classified.
2. **Streaming mode** (``stream=true``) — Returns a stream of SSE events,
   each carrying a ``StreamEvent`` payload.  Results are emitted one by one
   as soon as verification completes.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from opensift.models.assessment import ScoredResult, ValidationResult
from opensift.models.criteria import CriteriaResult

# ═══════════════════════════════════════════════════════════════════════════════
# Raw verification result (no classification)
# ═══════════════════════════════════════════════════════════════════════════════


class RawVerifiedResult(BaseModel):
    """A search result with its raw verification but without classification.

    Returned when ``classify=false`` — the verification assessments are
    included but no perfect/partial/reject label or weighted score is applied.
    """

    result: dict = Field(description="Original result item (ResultItem dict)")
    validation: ValidationResult = Field(description="LLM validation result")


# ═══════════════════════════════════════════════════════════════════════════════
# Complete mode response
# ═══════════════════════════════════════════════════════════════════════════════


class SearchResponse(BaseModel):
    """Complete search response returned to the client.

    Contains the full filtering funnel output:
      1. criteria_result: Generated search queries and screening criteria
      2. perfect_results: Results that fully match all criteria (when classify=true)
      3. partial_results: Results with partial matches (when classify=true)
      4. rejected_count: Number of results filtered out (when classify=true)
      5. raw_results: All verified results without classification (when classify=false)
      6. processing metadata
    """

    request_id: str = Field(description="Unique request identifier")
    status: str = Field(default="completed", description="Processing status")
    processing_time_ms: int = Field(default=0, description="Total processing time in ms")

    # Query decomposition
    query: str = Field(description="Original user query")
    criteria_result: CriteriaResult = Field(description="Generated search queries and criteria")

    # Classified results (when classify=true, default)
    perfect_results: list[ScoredResult] = Field(
        default_factory=list,
        description="Results that fully match all criteria (classify=true)",
    )
    partial_results: list[ScoredResult] = Field(
        default_factory=list,
        description="Results with partial matches (classify=true)",
    )
    rejected_count: int = Field(
        default=0,
        description="Number of results that did not meet criteria (classify=true)",
    )

    # Raw verified results (when classify=false)
    raw_results: list[RawVerifiedResult] = Field(
        default_factory=list,
        description="All verified results without classification (classify=false)",
    )

    # Stats
    total_scanned: int = Field(default=0, description="Total results retrieved from search")


# ═══════════════════════════════════════════════════════════════════════════════
# Plan-only response
# ═══════════════════════════════════════════════════════════════════════════════


class PlanResponse(BaseModel):
    """Response for a plan-only request.

    Returns the generated search queries and screening criteria without
    executing the search/verification pipeline.
    """

    request_id: str = Field(description="Unique request identifier")
    query: str = Field(description="Original user query")
    criteria_result: CriteriaResult = Field(description="Generated search queries and criteria")
    processing_time_ms: int = Field(default=0, description="Planning processing time in ms")


# ═══════════════════════════════════════════════════════════════════════════════
# Streaming mode events (SSE)
# ═══════════════════════════════════════════════════════════════════════════════


class StreamEvent(BaseModel):
    """A single Server-Sent Event payload for streaming mode.

    Event types:

    - ``criteria``  — Planning complete; carries ``CriteriaResult`` + total count.
    - ``result``    — One result verified + classified; carries ``ScoredResult``.
    - ``done``      — All results processed; carries final summary stats.
    - ``error``     — An error occurred; carries error detail.
    """

    event: str = Field(description="Event type: criteria | result | done | error")
    data: dict[str, Any] = Field(description="Event payload")


# ═══════════════════════════════════════════════════════════════════════════════
# Batch mode response
# ═══════════════════════════════════════════════════════════════════════════════


class BatchSearchResponse(BaseModel):
    """Response for a batch search request (multiple queries).

    Contains one ``SearchResponse`` per query, plus aggregate stats
    and optional exported data.
    """

    status: str = Field(default="completed", description="Overall batch status")
    processing_time_ms: int = Field(default=0, description="Total processing time in ms")
    total_queries: int = Field(description="Number of queries in the batch")
    results: list[SearchResponse] = Field(description="Per-query search responses")

    # Export
    export_format: str | None = Field(default=None, description="Export format (csv, json) if requested")
    export_data: str | None = Field(default=None, description="Exported data as a string (CSV text or JSON string)")
