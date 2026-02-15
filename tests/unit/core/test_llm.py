"""Tests for the LLM client utilities."""

from __future__ import annotations

from opensift.core.llm.client import LLMClient
from opensift.core.llm.prompts import format_criteria_xml


class TestLLMClientUtils:
    """Tests for LLM client utility methods."""

    def test_strip_code_fences_json(self) -> None:
        """Should strip ```json ... ``` fences."""
        text = '```json\n{"key": "value"}\n```'
        result = LLMClient._strip_code_fences(text)
        assert result == '{"key": "value"}'

    def test_strip_code_fences_plain(self) -> None:
        """Should strip ``` ... ``` fences."""
        text = '```\n{"key": "value"}\n```'
        result = LLMClient._strip_code_fences(text)
        assert result == '{"key": "value"}'

    def test_strip_code_fences_no_fences(self) -> None:
        """Should return text unchanged if no fences."""
        text = '{"key": "value"}'
        result = LLMClient._strip_code_fences(text)
        assert result == '{"key": "value"}'


class TestPromptUtils:
    """Tests for prompt formatting utilities."""

    def test_format_criteria_xml_single(self) -> None:
        criteria = ["The paper discusses solar energy."]
        result = format_criteria_xml(criteria)
        assert "<criterion_1>" in result
        assert "solar energy" in result

    def test_format_criteria_xml_multiple(self) -> None:
        criteria = ["First criterion.", "Second criterion."]
        result = format_criteria_xml(criteria)
        assert "<criterion_1>" in result
        assert "<criterion_2>" in result

    def test_format_criteria_xml_empty(self) -> None:
        result = format_criteria_xml([])
        assert result == "<criteria>\n</criteria>"
