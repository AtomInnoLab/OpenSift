"""Base search adapter — Abstract interface for all search engine connectors.

Every search backend must implement this interface to integrate with OpenSift.
The adapter is responsible for:
  1. Executing search queries against the backend
  2. Fetching individual documents
  3. Mapping raw results to the OpenSift standard document schema
  4. Reporting health status
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from opensift.models.document import StandardDocument
from opensift.models.query import SearchOptions


class AdapterHealth(BaseModel):
    """Health status of a search adapter."""

    status: str = Field(description="Health status: healthy, degraded, unhealthy")
    latency_ms: int = Field(default=0, description="Latency of last health check in ms")
    last_check: str | None = Field(default=None, description="ISO timestamp of last health check")
    error_rate: float = Field(default=0.0, description="Recent error rate (0.0 - 1.0)")
    message: str | None = Field(default=None, description="Additional health message")


class RawResults(BaseModel):
    """Raw search results from a backend before normalization."""

    total_hits: int = Field(default=0, description="Total number of matching documents")
    documents: list[dict[str, Any]] = Field(default_factory=list, description="Raw document dicts")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Backend-specific metadata")
    took_ms: int = Field(default=0, description="Backend query execution time in ms")


class SearchAdapter(ABC):
    """Abstract base class for search engine adapters.

    All adapters must implement:
      - search(): Execute a query and return raw results
      - fetch_document(): Retrieve a single document by ID
      - map_to_standard_schema(): Normalize raw results to StandardDocument
      - health_check(): Report adapter health status

    Adapters should be stateless and thread-safe. Connection pooling
    and configuration are handled during initialization.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter name (e.g., 'elasticsearch', 'solr')."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter (connections, pools, etc.).

        Called once during application startup.
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shut down the adapter.

        Called during application shutdown. Should close connections
        and release resources.
        """

    @abstractmethod
    async def search(self, query: str, options: SearchOptions) -> RawResults:
        """Execute a search query against the backend.

        Args:
            query: The search query string.
            options: Search behavior options.

        Returns:
            Raw search results from the backend.
        """

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve a single document by its ID.

        Args:
            doc_id: The document identifier.

        Returns:
            Raw document data as a dictionary.

        Raises:
            DocumentNotFoundError: If the document does not exist.
        """

    @abstractmethod
    def map_to_standard_schema(self, raw_result: dict[str, Any]) -> StandardDocument:
        """Map a raw backend result to the OpenSift standard document format.

        Args:
            raw_result: A single raw document from the backend.

        Returns:
            A normalized StandardDocument.
        """

    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Check the health of the search backend.

        Returns:
            Current health status of the adapter.
        """

    async def search_and_normalize(self, query: str, options: SearchOptions) -> list[StandardDocument]:
        """Search and normalize results in one step.

        Convenience method that calls search() and then maps all results
        to the standard schema.

        Args:
            query: The search query string.
            options: Search behavior options.

        Returns:
            List of normalized StandardDocuments.
        """
        raw = await self.search(query, options)
        return [self.map_to_standard_schema(doc) for doc in raw.documents]
