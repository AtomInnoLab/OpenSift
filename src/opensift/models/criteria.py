"""Criteria models — Screening criteria generated from user queries."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Criterion(BaseModel):
    """A single screening criterion for filtering search results.

    Each criterion is an independent, actionable rule that can be checked
    against a paper's title/abstract/metadata.
    """

    criterion_id: str = Field(description="Unique criterion identifier (e.g., criterion_1)")
    type: str = Field(description="Criterion type (task, method, topic, time, population, etc.)")
    name: str = Field(description="Concise label summarizing the criterion")
    description: str = Field(description="One-sentence rule defining the criterion")
    weight: float = Field(default=0.0, ge=0.0, le=1.0, description="Weight of this criterion (all weights sum to 1.0)")


class CriteriaResult(BaseModel):
    """Result of the criteria generation stage (query decomposition).

    Produced by the Planner from a user's natural language query.
    Contains search queries for retrieval and criteria for filtering.
    """

    search_queries: list[str] = Field(
        description="2-4 search queries for paper retrieval",
        min_length=1,
    )
    criteria: list[Criterion] = Field(
        description="1-4 screening criteria for result validation",
        min_length=1,
    )
