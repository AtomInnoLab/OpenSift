"""Base adapter interface — Abstract classes for search engine connectors."""

from opensift.adapters.base.adapter import SearchAdapter
from opensift.adapters.base.registry import AdapterRegistry

__all__ = ["AdapterRegistry", "SearchAdapter"]
