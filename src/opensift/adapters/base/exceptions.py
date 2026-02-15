"""Adapter-specific exceptions."""


class AdapterError(Exception):
    """Base exception for adapter errors."""


class ConnectionError(AdapterError):
    """Raised when the adapter cannot connect to the search backend."""


class DocumentNotFoundError(AdapterError):
    """Raised when a requested document does not exist."""


class QueryError(AdapterError):
    """Raised when a search query fails."""


class ConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid."""
