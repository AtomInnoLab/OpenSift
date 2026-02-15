"""Adapter Registry — Manages registration and retrieval of search adapters.

The registry is a central place to register adapter classes and create
adapter instances based on configuration. It supports lazy initialization
and health monitoring.
"""

from __future__ import annotations

import logging
from typing import Any

from opensift.adapters.base.adapter import AdapterHealth, SearchAdapter

logger = logging.getLogger(__name__)


class AdapterNotFoundError(Exception):
    """Raised when a requested adapter is not registered."""


class AdapterRegistry:
    """Registry for managing search adapter instances.

    The registry maintains both adapter class registrations and
    initialized adapter instances. It supports:
      - Registering adapter classes by name
      - Creating and initializing adapter instances from config
      - Retrieving active adapters by name
      - Health checking all registered adapters

    Example:
        >>> registry = AdapterRegistry()
        >>> registry.register("elasticsearch", ElasticsearchAdapter)
        >>> await registry.initialize_adapter("elasticsearch", config={"hosts": [...]})
        >>> adapter = registry.get("elasticsearch")
    """

    def __init__(self) -> None:
        self._classes: dict[str, type[SearchAdapter]] = {}
        self._instances: dict[str, SearchAdapter] = {}

    def register(self, name: str, adapter_class: type[SearchAdapter]) -> None:
        """Register an adapter class.

        Args:
            name: Unique name for this adapter type.
            adapter_class: The adapter class to register.
        """
        if name in self._classes:
            logger.warning("Overwriting existing adapter registration: %s", name)
        self._classes[name] = adapter_class
        logger.info("Registered adapter: %s", name)

    async def initialize_adapter(self, name: str, **kwargs: Any) -> SearchAdapter:
        """Create and initialize an adapter instance.

        Args:
            name: The registered adapter name.
            **kwargs: Configuration parameters passed to the adapter constructor.

        Returns:
            The initialized adapter instance.

        Raises:
            AdapterNotFoundError: If no adapter is registered under this name.
        """
        if name not in self._classes:
            raise AdapterNotFoundError(
                f"No adapter registered with name '{name}'. "
                f"Available adapters: {list(self._classes.keys())}"
            )

        adapter_class = self._classes[name]
        adapter = adapter_class(**kwargs)
        await adapter.initialize()
        self._instances[name] = adapter
        logger.info("Initialized adapter: %s", name)
        return adapter

    def get(self, name: str) -> SearchAdapter:
        """Get an initialized adapter instance by name.

        Args:
            name: The adapter name.

        Returns:
            The adapter instance.

        Raises:
            AdapterNotFoundError: If the adapter is not initialized.
        """
        if name not in self._instances:
            raise AdapterNotFoundError(
                f"Adapter '{name}' is not initialized. "
                f"Call initialize_adapter() first."
            )
        return self._instances[name]

    def get_default(self) -> SearchAdapter:
        """Get the first available adapter (convenience method).

        Returns:
            The first initialized adapter.

        Raises:
            AdapterNotFoundError: If no adapters are initialized.
        """
        if not self._instances:
            raise AdapterNotFoundError("No adapters are initialized.")
        return next(iter(self._instances.values()))

    async def health_check_all(self) -> dict[str, AdapterHealth]:
        """Run health checks on all initialized adapters.

        Returns:
            Dictionary mapping adapter names to their health status.
        """
        results: dict[str, AdapterHealth] = {}
        for name, adapter in self._instances.items():
            try:
                results[name] = await adapter.health_check()
            except Exception as e:
                results[name] = AdapterHealth(
                    status="unhealthy",
                    message=str(e),
                )
        return results

    async def shutdown_all(self) -> None:
        """Gracefully shut down all initialized adapters."""
        for name, adapter in self._instances.items():
            try:
                await adapter.shutdown()
                logger.info("Shut down adapter: %s", name)
            except Exception:
                logger.warning("Error shutting down adapter: %s", name, exc_info=True)
        self._instances.clear()

    @property
    def registered_adapters(self) -> list[str]:
        """List all registered adapter names."""
        return list(self._classes.keys())

    @property
    def active_adapters(self) -> list[str]:
        """List all initialized adapter names."""
        return list(self._instances.keys())
