"""Standard document model — Generic schema for search adapter results.

Adapters that do not provide a direct ``search_papers()`` method map their
raw results to this intermediate format.  The engine then converts it to
``PaperInfo`` for the verification pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata associated with a document."""

    source: str = Field(default="", description="Source identifier (e.g., index name, collection)")
    url: str | None = Field(default=None, description="Original document URL")
    published_date: datetime | None = Field(default=None, description="Document publication date")
    author: str | None = Field(default=None, description="Document author")
    language: str | None = Field(default=None, description="Document language code (ISO 639-1)")
    tags: list[str] = Field(default_factory=list, description="Associated tags or categories")
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional adapter-specific metadata")


class StandardDocument(BaseModel):
    """Normalized document format used across all adapters.

    Every search adapter must map its raw results to this standard schema,
    ensuring consistent processing in the engine pipeline.
    """

    id: str = Field(description="Unique document identifier")
    title: str = Field(description="Document title")
    content: str = Field(description="Full document content or relevant excerpt")
    snippet: str | None = Field(default=None, description="Short highlighted snippet")
    score: float = Field(default=0.0, description="Relevance score from search backend")
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata, description="Document metadata")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Timestamp of retrieval")
