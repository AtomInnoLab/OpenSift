"""API dependencies — Dependency injection for FastAPI endpoints."""

from __future__ import annotations

from opensift.core.engine import OpenSiftEngine

# Global engine instance (set during application lifespan)
_engine: OpenSiftEngine | None = None


def set_engine(engine: OpenSiftEngine | None) -> None:
    """Set the global engine instance (called during app lifespan)."""
    global _engine
    _engine = engine


def get_engine() -> OpenSiftEngine:
    """Get the global OpenSift engine instance.

    Returns:
        The initialized OpenSiftEngine.

    Raises:
        RuntimeError: If the engine is not initialized.
    """
    if _engine is None:
        raise RuntimeError("OpenSift engine not initialized. Is the server running?")
    return _engine
