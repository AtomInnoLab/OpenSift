"""Criteria models — Screening criteria generated from user queries."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# All valid criterion types returned by WisModel.
# The LLM may also produce new types not in this list; the field accepts any str.
CRITERION_TYPES = (
    "task",
    "method",
    "topic",
    "substance",
    "time",
    "population",
    "disease",
    "dataset",
    "document_type",
    "performance",
    "properties",
    "background",
    "affiliation",
    "location",
    "mechanism",
    "state",
    "publication_venue",
    "resource_property",
    "condition",
    "indicator",
    "person",
)

CriterionType = Literal[
    "task",
    "method",
    "topic",
    "substance",
    "time",
    "population",
    "disease",
    "dataset",
    "document_type",
    "performance",
    "properties",
    "background",
    "affiliation",
    "location",
    "mechanism",
    "state",
    "publication_venue",
    "resource_property",
    "condition",
    "indicator",
    "person",
]


class Criterion(BaseModel):
    """A single screening criterion for filtering search results.

    Each criterion is an independent, actionable rule that can be checked
    against a paper's title/abstract/metadata.
    """

    criterion_id: str = Field(description="Unique criterion identifier (e.g., criterion_1)")
    type: str = Field(
        description=(
            "Criterion type. Common types: task, method, topic, substance, time, "
            "population, disease, dataset, document_type, performance, properties, "
            "background, affiliation, location, mechanism, state, publication_venue, "
            "resource_property, condition, indicator, person"
        ),
    )
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
