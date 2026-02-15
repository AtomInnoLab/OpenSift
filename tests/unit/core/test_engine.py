"""Tests for the OpenSift engine (export, helper functions)."""

from __future__ import annotations

import csv
import io
import json

from opensift.core.engine import OpenSiftEngine, _detect_language
from opensift.models.assessment import (
    AssessmentType,
    CriterionAssessment,
    ResultClassification,
    ScoredResult,
    ValidationResult,
)
from opensift.models.criteria import CriteriaResult, Criterion
from opensift.models.response import SearchResponse

# ── Test data builders ───────────────────────────────────────────────────────


def _scored(title: str, cls: ResultClassification, score: float) -> ScoredResult:
    return ScoredResult(
        result={"title": title, "content": f"Content of {title}", "source_url": f"https://example.com/{title}"},
        validation=ValidationResult(
            criteria_assessment=[
                CriterionAssessment(
                    criterion_id="c1",
                    assessment=AssessmentType.SUPPORT,
                    explanation="OK",
                ),
            ],
            summary=f"Summary for {title}.",
        ),
        classification=cls,
        weighted_score=score,
    )


def _search_response(query: str, perfect: list[ScoredResult], partial: list[ScoredResult]) -> SearchResponse:
    return SearchResponse(
        request_id="req_export",
        status="completed",
        processing_time_ms=50,
        query=query,
        criteria_result=CriteriaResult(
            search_queries=[query],
            criteria=[Criterion(criterion_id="c1", type="topic", name="T", description="D", weight=1.0)],
        ),
        perfect_results=perfect,
        partial_results=partial,
        rejected_count=0,
        total_scanned=len(perfect) + len(partial),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Language detection helper
# ══════════════════════════════════════════════════════════════════════════════


class TestDetectLanguage:
    def test_english(self) -> None:
        assert _detect_language("solar nowcasting deep learning") == "English"

    def test_chinese(self) -> None:
        assert _detect_language("太阳能即时预报的深度学习方法") == "中文"

    def test_mixed_mostly_english(self) -> None:
        assert _detect_language("What is solar nowcasting?") == "English"

    def test_mixed_mostly_chinese(self) -> None:
        assert _detect_language("有哪些关于太阳能即时预报的论文") == "中文"


# ══════════════════════════════════════════════════════════════════════════════
# Export functionality
# ══════════════════════════════════════════════════════════════════════════════


class TestExportResults:
    """Tests for OpenSiftEngine._export_results."""

    def _responses(self) -> list[SearchResponse]:
        return [
            _search_response(
                "query A",
                perfect=[_scored("Paper 1", ResultClassification.PERFECT, 1.0)],
                partial=[_scored("Paper 2", ResultClassification.PARTIAL, 0.6)],
            ),
            _search_response(
                "query B",
                perfect=[_scored("Paper 3", ResultClassification.PERFECT, 0.9)],
                partial=[],
            ),
        ]

    def test_csv_export_header(self) -> None:
        data = OpenSiftEngine._export_results(self._responses(), "csv")
        reader = csv.reader(io.StringIO(data))
        header = next(reader)
        assert "query" in header
        assert "classification" in header
        assert "title" in header
        assert "summary" in header

    def test_csv_export_row_count(self) -> None:
        data = OpenSiftEngine._export_results(self._responses(), "csv")
        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
        # 1 header + 3 data rows
        assert len(rows) == 4

    def test_csv_export_content(self) -> None:
        data = OpenSiftEngine._export_results(self._responses(), "csv")
        assert "Paper 1" in data
        assert "Paper 2" in data
        assert "Paper 3" in data
        assert "query A" in data
        assert "query B" in data

    def test_json_export_structure(self) -> None:
        data = OpenSiftEngine._export_results(self._responses(), "json")
        rows = json.loads(data)
        assert isinstance(rows, list)
        assert len(rows) == 3

    def test_json_export_fields(self) -> None:
        data = OpenSiftEngine._export_results(self._responses(), "json")
        rows = json.loads(data)
        for row in rows:
            assert "query" in row
            assert "classification" in row
            assert "weighted_score" in row
            assert "title" in row
            assert "summary" in row

    def test_json_export_values(self) -> None:
        data = OpenSiftEngine._export_results(self._responses(), "json")
        rows = json.loads(data)
        titles = {r["title"] for r in rows}
        assert titles == {"Paper 1", "Paper 2", "Paper 3"}

    def test_unknown_format_returns_empty(self) -> None:
        data = OpenSiftEngine._export_results(self._responses(), "xml")
        assert data == ""
