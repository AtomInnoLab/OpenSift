"""Shared test fixtures and configuration."""

from __future__ import annotations

import pytest

from opensift.config.settings import Settings
from opensift.models.assessment import (
    AssessmentType,
    CriterionAssessment,
    Evidence,
    ValidationResult,
)
from opensift.models.criteria import CriteriaResult, Criterion
from opensift.models.paper import PaperInfo
from opensift.models.query import SearchContext, SearchOptions, SearchRequest
from opensift.models.result import ResultItem


@pytest.fixture
def settings() -> Settings:
    """Create a test Settings instance with defaults."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        debug=True,
        ai={"api_key": "test-key", "fallback_to_local": True},
    )


@pytest.fixture
def sample_request() -> SearchRequest:
    """Create a sample search request for testing."""
    return SearchRequest(
        query="有哪些关于太阳能即时预报的论文？",
        options=SearchOptions(
            decompose=True,
            verify=True,
            max_results=10,
        ),
        context=SearchContext(
            user_domain="energy",
        ),
    )


@pytest.fixture
def simple_request() -> SearchRequest:
    """Create a simple search request (no decomposition)."""
    return SearchRequest(
        query="solar nowcasting papers",
        options=SearchOptions(
            decompose=False,
            verify=False,
        ),
    )


@pytest.fixture
def sample_criteria() -> list[Criterion]:
    """Create sample screening criteria."""
    return [
        Criterion(
            criterion_id="criterion_1",
            type="task",
            name="Turbulence modeling analysis",
            description="The result analyzes or applies turbulence modeling techniques.",
            weight=0.5,
        ),
        Criterion(
            criterion_id="criterion_2",
            type="topic",
            name="Large language model focus",
            description="The result involves large language models (LLMs) as a primary subject.",
            weight=0.5,
        ),
    ]


@pytest.fixture
def sample_criteria_result() -> CriteriaResult:
    """Create a sample CriteriaResult."""
    return CriteriaResult(
        search_queries=[
            '"solar nowcasting"',
            '"solar" AND "nowcasting"',
            "solar nowcasting",
        ],
        criteria=[
            Criterion(
                criterion_id="criterion_1",
                type="task",
                name="Solar nowcasting focus",
                description="The result addresses or proposes methods for solar nowcasting.",
                weight=1.0,
            ),
        ],
    )


# ── PaperInfo fixtures (domain-specific, used by AtomWalker adapter tests) ──


@pytest.fixture
def sample_paper_turbulence() -> PaperInfo:
    """Create a sample turbulence paper (NOT about LLMs)."""
    return PaperInfo(
        title="A DDES Model with Subgrid-scale Eddy Viscosity for Turbulent Flow",
        authors="Puxian Ding, Xue-Gang Zhou",
        affiliations="Academy of Building Energy Efficiency, Guangzhou University",
        conference_journal="SOSP",
        conference_journal_type="Conference",
        research_field="Fluid Dynamics and Turbulent Flows; Engineering; Computational Mechanics",
        doi="https://doi.org/10.77641577b0",
        publication_date="2022",
        abstract=(
            "The original (delayed) detached-eddy simulation ((D)DES), a widely used and "
            "efficient hybrid turbulence method, is confronted with some flaws containing "
            "grid-induced separation (GIS), log-layer mismatch (LLM), slow RANS-LES transition."
        ),
        citation_count=5,
        source_url="https://openalex.org/W4221069823",
    )


@pytest.fixture
def sample_paper_solar() -> PaperInfo:
    """Create a sample solar nowcasting paper."""
    return PaperInfo(
        title="Deep Learning for Solar Irradiance Nowcasting",
        authors="Jane Doe, John Smith",
        affiliations="MIT, Stanford University",
        conference_journal="Solar Energy",
        conference_journal_type="SCI",
        research_field="Renewable Energy; Machine Learning",
        doi="https://doi.org/10.1016/j.solener.2024.01.001",
        publication_date="2024",
        abstract=(
            "We propose a deep learning framework for short-term solar irradiance nowcasting "
            "using satellite imagery and ground station data. Our model achieves state-of-the-art "
            "performance on 15-minute and 1-hour prediction horizons."
        ),
        citation_count=12,
        source_url="https://example.com/solar-nowcasting",
    )


# ── ResultItem fixtures (generic, used by verifier/classifier tests) ──


@pytest.fixture
def result_turbulence(sample_paper_turbulence: PaperInfo) -> ResultItem:
    """Generic ResultItem from the turbulence paper."""
    return sample_paper_turbulence.to_result_item()


@pytest.fixture
def result_solar(sample_paper_solar: PaperInfo) -> ResultItem:
    """Generic ResultItem from the solar paper."""
    return sample_paper_solar.to_result_item()


@pytest.fixture
def support_validation() -> ValidationResult:
    """Create a validation result with full support."""
    return ValidationResult(
        criteria_assessment=[
            CriterionAssessment(
                criterion_id="criterion_1",
                assessment=AssessmentType.SUPPORT,
                explanation="Result directly addresses solar nowcasting.",
                evidence=[
                    Evidence(source="title", text="Deep Learning for Solar Irradiance Nowcasting"),
                    Evidence(source="content", text="short-term solar irradiance nowcasting"),
                ],
            ),
        ],
        summary="Result focuses on solar irradiance nowcasting using deep learning.",
    )


@pytest.fixture
def reject_validation() -> ValidationResult:
    """Create a validation result with rejection."""
    return ValidationResult(
        criteria_assessment=[
            CriterionAssessment(
                criterion_id="criterion_1",
                assessment=AssessmentType.REJECT,
                explanation="Result is about turbulence modeling, not solar nowcasting.",
                evidence=[
                    Evidence(source="title", text="DDES Model for Turbulent Flow"),
                ],
            ),
        ],
        summary="Result is about turbulence simulation, unrelated to solar nowcasting.",
    )


@pytest.fixture
def mixed_validation() -> ValidationResult:
    """Create a validation result with mixed assessments (for multi-criteria)."""
    return ValidationResult(
        criteria_assessment=[
            CriterionAssessment(
                criterion_id="criterion_1",
                assessment=AssessmentType.SUPPORT,
                explanation="Result applies turbulence modeling techniques.",
                evidence=[
                    Evidence(source="title", text="DDES Model for Turbulent Flow"),
                ],
            ),
            CriterionAssessment(
                criterion_id="criterion_2",
                assessment=AssessmentType.REJECT,
                explanation="Result is not about large language models.",
                evidence=[
                    Evidence(source="research_field", text="Fluid Dynamics and Turbulent Flows"),
                ],
            ),
        ],
        summary="Result discusses turbulence modeling but not LLMs.",
    )
