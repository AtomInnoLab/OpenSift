"""Tests for the Result Classifier (perfect/partial/reject logic)."""

from __future__ import annotations

import pytest

from opensift.core.classifier import ResultClassifier
from opensift.models.assessment import (
    AssessmentType,
    CriterionAssessment,
    ResultClassification,
    ValidationResult,
)
from opensift.models.criteria import Criterion
from opensift.models.result import ResultItem


class TestSingleCriterionClassification:
    """Tests for single-criterion classification rules."""

    @pytest.fixture
    def single_criterion(self) -> list[Criterion]:
        return [
            Criterion(
                criterion_id="criterion_1",
                type="task",
                name="Solar nowcasting",
                description="Result addresses solar nowcasting.",
                weight=1.0,
            ),
        ]

    @pytest.fixture
    def item(self) -> ResultItem:
        return ResultItem(title="Test Result", content="Test description")

    def test_support_is_perfect(self, item: ResultItem, single_criterion: list[Criterion]) -> None:
        """Single criterion: support → perfect."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(
                    criterion_id="criterion_1",
                    assessment=AssessmentType.SUPPORT,
                    explanation="Matches",
                ),
            ],
            summary="Relevant result.",
        )
        result = ResultClassifier.classify(item, validation, single_criterion)
        assert result.classification == ResultClassification.PERFECT
        assert result.weighted_score == 1.0

    def test_somewhat_support_is_partial(self, item: ResultItem, single_criterion: list[Criterion]) -> None:
        """Single criterion: somewhat_support → partial."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(
                    criterion_id="criterion_1",
                    assessment=AssessmentType.SOMEWHAT_SUPPORT,
                    explanation="Partially matches",
                ),
            ],
            summary="Somewhat relevant.",
        )
        result = ResultClassifier.classify(item, validation, single_criterion)
        assert result.classification == ResultClassification.PARTIAL
        assert result.weighted_score == 0.5

    def test_reject_is_reject(self, item: ResultItem, single_criterion: list[Criterion]) -> None:
        """Single criterion: reject → reject."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(
                    criterion_id="criterion_1",
                    assessment=AssessmentType.REJECT,
                    explanation="Not relevant",
                ),
            ],
            summary="Irrelevant result.",
        )
        result = ResultClassifier.classify(item, validation, single_criterion)
        assert result.classification == ResultClassification.REJECT
        assert result.weighted_score == 0.0

    def test_insufficient_is_reject(self, item: ResultItem, single_criterion: list[Criterion]) -> None:
        """Single criterion: insufficient_information → reject."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(
                    criterion_id="criterion_1",
                    assessment=AssessmentType.INSUFFICIENT_INFORMATION,
                    explanation="Cannot determine",
                ),
            ],
            summary="Cannot determine relevance.",
        )
        result = ResultClassifier.classify(item, validation, single_criterion)
        assert result.classification == ResultClassification.REJECT


class TestMultiCriterionClassification:
    """Tests for multi-criterion classification rules."""

    @pytest.fixture
    def multi_criteria(self) -> list[Criterion]:
        return [
            Criterion(
                criterion_id="criterion_1",
                type="task",
                name="Turbulence modeling",
                description="Result applies turbulence modeling.",
                weight=0.5,
            ),
            Criterion(
                criterion_id="criterion_2",
                type="topic",
                name="LLM focus",
                description="Result involves large language models.",
                weight=0.5,
            ),
        ]

    @pytest.fixture
    def item(self) -> ResultItem:
        return ResultItem(title="Test Result", content="Test description")

    def test_all_support_is_perfect(self, item: ResultItem, multi_criteria: list[Criterion]) -> None:
        """All support → perfect."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(criterion_id="criterion_1", assessment=AssessmentType.SUPPORT, explanation="ok"),
                CriterionAssessment(criterion_id="criterion_2", assessment=AssessmentType.SUPPORT, explanation="ok"),
            ],
            summary="Full match.",
        )
        result = ResultClassifier.classify(item, validation, multi_criteria)
        assert result.classification == ResultClassification.PERFECT
        assert result.weighted_score == 1.0

    def test_one_support_one_reject_is_partial(self, item: ResultItem, multi_criteria: list[Criterion]) -> None:
        """One support + one reject → partial (non-time type has support)."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(criterion_id="criterion_1", assessment=AssessmentType.SUPPORT, explanation="ok"),
                CriterionAssessment(criterion_id="criterion_2", assessment=AssessmentType.REJECT, explanation="no"),
            ],
            summary="Partial match.",
        )
        result = ResultClassifier.classify(item, validation, multi_criteria)
        assert result.classification == ResultClassification.PARTIAL
        assert result.weighted_score == 0.5

    def test_all_reject_is_reject(self, item: ResultItem, multi_criteria: list[Criterion]) -> None:
        """All reject → reject."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(criterion_id="criterion_1", assessment=AssessmentType.REJECT, explanation="no"),
                CriterionAssessment(criterion_id="criterion_2", assessment=AssessmentType.REJECT, explanation="no"),
            ],
            summary="No match.",
        )
        result = ResultClassifier.classify(item, validation, multi_criteria)
        assert result.classification == ResultClassification.REJECT
        assert result.weighted_score == 0.0

    def test_time_type_only_support_is_reject(self, item: ResultItem) -> None:
        """If only time-type criterion is support, still reject."""
        criteria = [
            Criterion(criterion_id="criterion_1", type="time", name="Recency", description="After 2020", weight=0.3),
            Criterion(criterion_id="criterion_2", type="topic", name="Topic", description="About AI", weight=0.7),
        ]
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(criterion_id="criterion_1", assessment=AssessmentType.SUPPORT, explanation="ok"),
                CriterionAssessment(criterion_id="criterion_2", assessment=AssessmentType.REJECT, explanation="no"),
            ],
            summary="Only time criterion matched.",
        )
        result = ResultClassifier.classify(item, validation, criteria)
        assert result.classification == ResultClassification.REJECT

    def test_somewhat_support_non_time_is_partial(self, item: ResultItem, multi_criteria: list[Criterion]) -> None:
        """somewhat_support on non-time criterion → partial."""
        validation = ValidationResult(
            criteria_assessment=[
                CriterionAssessment(
                    criterion_id="criterion_1",
                    assessment=AssessmentType.SOMEWHAT_SUPPORT,
                    explanation="partial",
                ),
                CriterionAssessment(
                    criterion_id="criterion_2",
                    assessment=AssessmentType.REJECT,
                    explanation="no",
                ),
            ],
            summary="Partial match.",
        )
        result = ResultClassifier.classify(item, validation, multi_criteria)
        assert result.classification == ResultClassification.PARTIAL


class TestClassifyBatch:
    """Tests for batch classification and sorting."""

    def test_batch_sorted_by_priority(self) -> None:
        """Results should be sorted: perfect > partial > reject."""
        criteria = [
            Criterion(criterion_id="criterion_1", type="topic", name="Topic", description="Test", weight=1.0),
        ]
        items = [ResultItem(title=f"Result {i}") for i in range(3)]
        validations = [
            ValidationResult(
                criteria_assessment=[
                    CriterionAssessment(criterion_id="criterion_1", assessment=AssessmentType.REJECT, explanation="no")
                ],
                summary="reject",
            ),
            ValidationResult(
                criteria_assessment=[
                    CriterionAssessment(
                        criterion_id="criterion_1", assessment=AssessmentType.SUPPORT, explanation="yes"
                    )
                ],
                summary="perfect",
            ),
            ValidationResult(
                criteria_assessment=[
                    CriterionAssessment(
                        criterion_id="criterion_1", assessment=AssessmentType.SOMEWHAT_SUPPORT, explanation="maybe"
                    )
                ],
                summary="partial",
            ),
        ]

        results = ResultClassifier.classify_batch(items, validations, criteria)
        assert results[0].classification == ResultClassification.PERFECT
        assert results[1].classification == ResultClassification.PARTIAL
        assert results[2].classification == ResultClassification.REJECT
