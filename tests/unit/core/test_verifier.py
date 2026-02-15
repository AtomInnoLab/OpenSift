"""Tests for the Evidence Verifier (LLM-based result validation)."""

from __future__ import annotations

import pytest

from opensift.config.settings import Settings
from opensift.core.verifier.verifier import EvidenceVerifier
from opensift.models.assessment import AssessmentType, ValidationResult
from opensift.models.criteria import Criterion
from opensift.models.result import ResultItem


class TestEvidenceVerifier:
    """Tests for EvidenceVerifier."""

    @pytest.fixture
    def verifier(self, settings: Settings) -> EvidenceVerifier:
        return EvidenceVerifier(settings)

    @pytest.mark.asyncio
    async def test_fallback_validation(
        self,
        verifier: EvidenceVerifier,
        result_turbulence: ResultItem,
        sample_criteria: list[Criterion],
    ) -> None:
        """Without LLM, should return insufficient_information for all criteria."""
        result = await verifier.verify(
            result_turbulence,
            sample_criteria,
            "test query",
        )
        assert isinstance(result, ValidationResult)
        assert len(result.criteria_assessment) == len(sample_criteria)
        for a in result.criteria_assessment:
            assert a.assessment == AssessmentType.INSUFFICIENT_INFORMATION

    @pytest.mark.asyncio
    async def test_verify_batch(
        self,
        verifier: EvidenceVerifier,
        result_turbulence: ResultItem,
        result_solar: ResultItem,
        sample_criteria: list[Criterion],
    ) -> None:
        """Batch verification should return one result per item."""
        results = await verifier.verify_batch(
            [result_turbulence, result_solar],
            sample_criteria,
            "test query",
        )
        assert len(results) == 2
        for r in results:
            assert isinstance(r, ValidationResult)

    @pytest.mark.asyncio
    async def test_backward_compat_verify_papers(
        self,
        verifier: EvidenceVerifier,
        sample_paper_turbulence,
        sample_paper_solar,
        sample_criteria: list[Criterion],
    ) -> None:
        """Backward-compatible verify_papers() accepts PaperInfo objects."""
        results = await verifier.verify_papers(
            [sample_paper_turbulence, sample_paper_solar],
            sample_criteria,
            "test query",
        )
        assert len(results) == 2
        for r in results:
            assert isinstance(r, ValidationResult)

    def test_parse_validation_response(
        self,
        verifier: EvidenceVerifier,
        sample_criteria: list[Criterion],
    ) -> None:
        """Test parsing a typical LLM validation response."""
        raw = {
            "criteria_assessment": [
                {
                    "criterion_id": "criterion_1",
                    "assessment": "support",
                    "explanation": "Result addresses turbulence modeling.",
                    "evidence": [
                        {"source": "title", "text": "DDES Model for Turbulent Flow"},
                    ],
                },
                {
                    "criterion_id": "criterion_2",
                    "assessment": "reject",
                    "explanation": "Result is not about LLMs.",
                    "evidence": [
                        {"source": "research_field", "text": "Fluid Dynamics"},
                    ],
                },
            ],
            "summary": "Result discusses turbulence modeling, not LLMs.",
        }
        result = verifier._parse_validation_response(raw, sample_criteria)
        assert len(result.criteria_assessment) == 2
        assert result.criteria_assessment[0].assessment == AssessmentType.SUPPORT
        assert result.criteria_assessment[1].assessment == AssessmentType.REJECT
        assert result.summary == "Result discusses turbulence modeling, not LLMs."

    def test_parse_invalid_assessment_fallback(
        self,
        verifier: EvidenceVerifier,
        sample_criteria: list[Criterion],
    ) -> None:
        """Invalid assessment strings should default to insufficient_information."""
        raw = {
            "criteria_assessment": [
                {
                    "criterion_id": "criterion_1",
                    "assessment": "invalid_value",
                    "explanation": "test",
                },
            ],
            "summary": "test",
        }
        result = verifier._parse_validation_response(raw, sample_criteria)
        assert result.criteria_assessment[0].assessment == AssessmentType.INSUFFICIENT_INFORMATION

    def test_fallback_validation_static(
        self,
        verifier: EvidenceVerifier,
        sample_criteria: list[Criterion],
    ) -> None:
        """Static fallback should mark all as insufficient_information."""
        result = EvidenceVerifier._fallback_validation(sample_criteria)
        assert len(result.criteria_assessment) == 2
        for a in result.criteria_assessment:
            assert a.assessment == AssessmentType.INSUFFICIENT_INFORMATION
