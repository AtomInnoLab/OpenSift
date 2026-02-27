"""Assessment models — LLM-based validation results for search results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AssessmentType(str, Enum):
    """Assessment result for a single criterion."""

    SUPPORT = "support"
    REJECT = "reject"
    SOMEWHAT_SUPPORT = "somewhat_support"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class Evidence(BaseModel):
    """A piece of evidence extracted from the search result."""

    source: str = Field(description="Field the evidence was extracted from (title, content, etc.)")
    text: str = Field(description="Verbatim text from the result")


class CriterionAssessment(BaseModel):
    """Assessment of a single criterion against a search result."""

    criterion_id: str = Field(description="ID of the criterion being assessed")
    assessment: AssessmentType = Field(description="Assessment result")
    explanation: str = Field(description="Why the criterion is/isn't met")
    evidence: list[Evidence] = Field(default_factory=list, description="Supporting evidence from the result")


class ValidationResult(BaseModel):
    """Complete validation result for a search result against all criteria.

    Produced by the Verifier for each result item.
    """

    criteria_assessment: list[CriterionAssessment] = Field(description="Per-criterion assessment results")
    summary: str = Field(description="Overall summary: result content + alignment with user query")


class ResultClassification(str, Enum):
    """Final classification of a search result after verification.

    - PERFECT: All criteria fully supported.
    - PARTIAL: At least one criterion supported/somewhat_supported (non-time type).
    - REJECT: Does not meet minimum criteria — should not be displayed.
    """

    PERFECT = "perfect"
    PARTIAL = "partial"
    REJECT = "reject"


class ScoredResult(BaseModel):
    """A search result with its validation and final classification.

    This is the output of the full filtering funnel for one result item.
    """

    result: dict = Field(description="Original result item (ResultItem dict)")
    validation: ValidationResult = Field(description="LLM validation result")
    classification: ResultClassification = Field(description="Final classification")
    weighted_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Weighted score based on criteria weights and assessments",
    )
