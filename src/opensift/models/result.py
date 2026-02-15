"""Result item model — Generic, domain-agnostic search result for verification.

Any search result (academic paper, product, news article, document, etc.)
is represented as a ``ResultItem`` before entering the verification pipeline.
Domain-specific adapters produce their own rich types (e.g. ``PaperInfo``)
and convert them to ``ResultItem`` for the verifier.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResultItem(BaseModel):
    """A search result item to be verified against screening criteria.

    This is the generic representation that the verifier operates on.
    It consists of three common fields (``title``, ``content``, ``source_url``)
    plus a free-form ``fields`` dict for any additional domain-specific
    metadata.

    The ``result_type`` field controls which prompt template the verifier
    uses:

    - ``"paper"`` — the specialised academic-paper prompt with fixed
      ``<paper_info>`` XML fields (title, authors, affiliations, …).
    - any other value — the generic prompt that dynamically renders
      all fields from ``fields``.

    Examples:
        Academic paper (type = "paper")::

            ResultItem(
                result_type="paper",
                title="Deep Learning for Solar Nowcasting",
                content="We propose a framework for short-term solar ...",
                source_url="https://doi.org/10.1016/...",
                fields={
                    "authors": "Jane Doe, John Smith",
                    "affiliations": "MIT, Stanford",
                    "publication_date": "2024",
                    "conference_journal": "Solar Energy",
                    ...
                },
            )

        Product listing (type = "generic")::

            ResultItem(
                title="Wireless Noise-Cancelling Headphones",
                content="Premium over-ear headphones with 30-hour battery ...",
                source_url="https://shop.example.com/headphones/123",
                fields={
                    "brand": "AudioPro",
                    "price": "$299",
                    "category": "Electronics > Audio",
                    ...
                },
            )
    """

    result_type: str = Field(
        default="generic",
        description=(
            "Type of the search result, determines which prompt template "
            "the verifier uses. Built-in types: 'paper', 'generic'."
        ),
    )
    title: str = Field(default="N/A", description="Title or heading of the result")
    content: str = Field(
        default="N/A",
        description="Main text body (abstract, description, body text, etc.)",
    )
    source_url: str = Field(default="N/A", description="Source URL")
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional domain-specific fields as key-value pairs",
    )

    def to_prompt_xml(self) -> str:
        """Render this result item as XML for the verification prompt.

        Returns:
            XML string with all non-empty fields.
        """
        parts = ["<result_info>"]
        parts.append(f"    <title>{self.title}</title>")
        parts.append(f"    <content>{self.content}</content>")
        if self.source_url and self.source_url != "N/A":
            parts.append(f"    <source_url>{self.source_url}</source_url>")
        for key, value in self.fields.items():
            str_value = str(value) if value is not None else ""
            if str_value and str_value != "N/A":
                parts.append(f"    <{key}>{str_value}</{key}>")
        parts.append("</result_info>")
        return "\n".join(parts)
