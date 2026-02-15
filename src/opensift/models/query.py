"""Query and search request models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchOptions(BaseModel):
    """Options controlling search behavior."""

    decompose: bool = Field(default=True, description="Enable query decomposition into search queries and criteria")
    verify: bool = Field(default=True, description="Enable LLM-based result verification against criteria")
    classify: bool = Field(default=True, description="Enable classification (perfect/partial/reject). When false, returns raw verification results without classification")
    stream: bool = Field(default=False, description="Enable streaming mode — emit each result as it is verified via SSE")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum number of results to return")
    recency_filter: str | None = Field(default=None, description="Recency filter (e.g., '1y', '6m', '30d')")
    adapters: list[str] | None = Field(default=None, description="Specific adapters to use (None = default)")
    timeout_seconds: float = Field(default=30.0, gt=0, description="Maximum request processing time")


class SearchContext(BaseModel):
    """Contextual information to refine search behavior."""

    user_domain: str | None = Field(default=None, description="User's domain (e.g., 'energy', 'biomedical')")
    preferred_sources: list[str] = Field(default_factory=list, description="Preferred source domains")
    excluded_sources: list[str] = Field(default_factory=list, description="Sources to exclude")
    language: str = Field(default="en", description="Preferred response language")
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional context parameters")


class SearchRequest(BaseModel):
    """Incoming search request from the API."""

    query: str = Field(description="Natural language search query", min_length=1, max_length=2000)
    options: SearchOptions = Field(default_factory=SearchOptions, description="Search behavior options")
    context: SearchContext = Field(default_factory=SearchContext, description="Search context")


class BatchSearchRequest(BaseModel):
    """Batch search request — multiple queries in one call."""

    queries: list[str] = Field(
        description="List of natural language search queries",
        min_length=1,
        max_length=20,
    )
    options: SearchOptions = Field(
        default_factory=SearchOptions,
        description="Shared search options applied to all queries",
    )
    context: SearchContext = Field(
        default_factory=SearchContext,
        description="Shared search context",
    )
    export_format: str | None = Field(
        default=None,
        description="Export format: 'csv' or 'json'. If set, response includes exported data.",
    )
