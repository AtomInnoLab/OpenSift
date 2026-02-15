"""Result Classifier — Determines perfect/partial/reject for validated results.

Classification rules:
  - When criteria count == 1:
      support → perfect
      somewhat_support → partial
      reject or insufficient_information → reject

  - When criteria count > 1:
      ALL assessments are support → perfect
      At least one support or somewhat_support (with non-time type) → partial
      Everything else → reject
"""

from __future__ import annotations

import logging

from opensift.models.assessment import (
    AssessmentType,
    ResultClassification,
    ScoredResult,
    ValidationResult,
)
from opensift.models.criteria import Criterion
from opensift.models.result import ResultItem

logger = logging.getLogger(__name__)


class ResultClassifier:
    """Classifies validated search results as perfect, partial, or reject.

    Uses the assessment results and criteria metadata (types, weights) to
    determine the final classification and weighted score for each result.
    """

    @staticmethod
    def classify(
        item: ResultItem,
        validation: ValidationResult,
        criteria: list[Criterion],
    ) -> ScoredResult:
        """Classify a single result based on its validation.

        Args:
            item: The search result item.
            validation: LLM validation result.
            criteria: The screening criteria (needed for types and weights).

        Returns:
            A ScoredResult with classification and weighted score.
        """
        assessments = validation.criteria_assessment
        criteria_count = len(criteria)

        # Build a lookup from criterion_id to criterion metadata
        criteria_map = {c.criterion_id: c for c in criteria}

        # Determine classification
        if criteria_count == 1:
            classification = ResultClassifier._classify_single(assessments)
        else:
            classification = ResultClassifier._classify_multiple(assessments, criteria_map)

        # Calculate weighted score
        weighted_score = ResultClassifier._calculate_weighted_score(assessments, criteria_map)

        return ScoredResult(
            result=item.model_dump(),
            validation=validation,
            classification=classification,
            weighted_score=round(weighted_score, 4),
        )

    @staticmethod
    def classify_batch(
        items: list[ResultItem],
        validations: list[ValidationResult],
        criteria: list[Criterion],
    ) -> list[ScoredResult]:
        """Classify a batch of results.

        Args:
            items: Search result items.
            validations: Validation results (same order as items).
            criteria: Screening criteria.

        Returns:
            List of ScoredResults with classifications.
        """
        results: list[ScoredResult] = []
        for item, validation in zip(items, validations, strict=True):
            scored = ResultClassifier.classify(item, validation, criteria)
            results.append(scored)

        # Sort by classification priority (perfect > partial > reject), then by score
        priority = {
            ResultClassification.PERFECT: 0,
            ResultClassification.PARTIAL: 1,
            ResultClassification.REJECT: 2,
        }
        results.sort(key=lambda s: (priority[s.classification], -s.weighted_score))

        return results

    @staticmethod
    def _classify_single(assessments: list) -> ResultClassification:
        """Classification for a single-criterion scenario.

        support → perfect
        somewhat_support → partial
        anything else → reject
        """
        if not assessments:
            return ResultClassification.REJECT

        assessment = assessments[0].assessment

        if assessment == AssessmentType.SUPPORT:
            return ResultClassification.PERFECT
        elif assessment == AssessmentType.SOMEWHAT_SUPPORT:
            return ResultClassification.PARTIAL
        else:
            return ResultClassification.REJECT

    @staticmethod
    def _classify_multiple(assessments: list, criteria_map: dict) -> ResultClassification:
        """Classification for multi-criteria scenario.

        ALL support → perfect
        At least one support/somewhat_support (non-time type) → partial
        Everything else → reject
        """
        if not assessments:
            return ResultClassification.REJECT

        # Check if ALL are support → perfect
        all_support = all(a.assessment == AssessmentType.SUPPORT for a in assessments)
        if all_support:
            return ResultClassification.PERFECT

        # Check if at least one support/somewhat_support with non-time type → partial
        for a in assessments:
            if a.assessment in (AssessmentType.SUPPORT, AssessmentType.SOMEWHAT_SUPPORT):
                criterion = criteria_map.get(a.criterion_id)
                # Non-time criterion has support/somewhat_support
                if criterion and criterion.type != "time":
                    return ResultClassification.PARTIAL

        return ResultClassification.REJECT

    @staticmethod
    def _calculate_weighted_score(assessments: list, criteria_map: dict) -> float:
        """Calculate weighted score based on assessments and criteria weights.

        Score mapping:
          support → 1.0
          somewhat_support → 0.5
          insufficient_information → 0.0
          reject → 0.0
        """
        score_map = {
            AssessmentType.SUPPORT: 1.0,
            AssessmentType.SOMEWHAT_SUPPORT: 0.5,
            AssessmentType.INSUFFICIENT_INFORMATION: 0.0,
            AssessmentType.REJECT: 0.0,
        }

        total = 0.0
        for a in assessments:
            criterion = criteria_map.get(a.criterion_id)
            weight = criterion.weight if criterion else 0.0
            total += score_map.get(a.assessment, 0.0) * weight

        return min(1.0, total)
