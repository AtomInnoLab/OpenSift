"""Paper models — Academic paper metadata (domain-specific search result).

``PaperInfo`` is the rich, academic-specific schema returned by scholarly
search adapters (e.g. AtomWalker).  It can be converted to the generic
``ResultItem`` via :meth:`to_result_item` before entering the verifier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from opensift.models.result import ResultItem


class PaperInfo(BaseModel):
    """Metadata of an academic paper.

    Fields that are unknown should be set to ``'N/A'``.
    """

    title: str = Field(default="N/A", description="Paper title")
    authors: str = Field(default="N/A", description="Author list, comma-separated")
    affiliations: str = Field(default="N/A", description="Author affiliations/institutions")
    conference_journal: str = Field(default="N/A", description="Conference or journal name")
    conference_journal_type: str = Field(
        default="N/A",
        description="Publication type: SCI, SCIE, arxiv, Conference, etc.",
    )
    research_field: str = Field(default="N/A", description="Research field(s), semicolon-separated")
    doi: str = Field(default="N/A", description="DOI link")
    publication_date: str = Field(default="N/A", description="Publication date/year")
    abstract: str = Field(default="N/A", description="Paper abstract")
    citation_count: int = Field(default=0, description="Citation count")
    source_url: str = Field(default="N/A", description="Source URL")

    def to_result_item(self) -> ResultItem:
        """Convert to the generic ``ResultItem`` for the verification pipeline.

        Maps academic-specific fields into the generic ``fields`` dict.
        """
        from opensift.models.result import ResultItem

        fields: dict[str, str] = {}
        if self.authors != "N/A":
            fields["authors"] = self.authors
        if self.affiliations != "N/A":
            fields["affiliations"] = self.affiliations
        if self.conference_journal != "N/A":
            fields["conference_journal"] = self.conference_journal
        if self.conference_journal_type != "N/A":
            fields["conference_journal_type"] = self.conference_journal_type
        if self.research_field != "N/A":
            fields["research_field"] = self.research_field
        if self.doi != "N/A":
            fields["doi"] = self.doi
        if self.publication_date != "N/A":
            fields["publication_date"] = self.publication_date
        if self.citation_count > 0:
            fields["citation_count"] = str(self.citation_count)

        return ResultItem(
            result_type="paper",
            title=self.title,
            content=self.abstract,
            source_url=self.source_url,
            fields=fields,
        )
