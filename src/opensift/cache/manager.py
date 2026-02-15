"""Cache Manager — Redis-backed caching for query plans and search results.

Provides a unified caching interface with configurable TTL per cache type.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from opensift.config.settings import CacheSettings

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching for OpenSift components.

    Supports Redis and in-memory backends with configurable TTL
    for different cache types.

    Attributes:
        settings: Cache configuration.
    """

    def __init__(self, settings: CacheSettings) -> None:
        self.settings = settings
        self._client: Any = None
        self._memory_cache: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize the cache backend."""
        if self.settings.backend == "redis":
            try:
                import redis.asyncio as aioredis

                self._client = aioredis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                )
                # Test connection
                await self._client.ping()
                logger.info("Connected to Redis cache at %s", self.settings.redis_url)
            except ImportError:
                logger.warning("redis package not available, falling back to memory cache")
                self.settings.backend = "memory"
            except Exception:
                logger.warning("Failed to connect to Redis, falling back to memory cache", exc_info=True)
                self.settings.backend = "memory"
        else:
            logger.info("Using in-memory cache backend")

    async def shutdown(self) -> None:
        """Close cache connections."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Any | None:
        """Retrieve a value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found.
        """
        try:
            if self.settings.backend == "redis" and self._client:
                value = await self._client.get(key)
                return json.loads(value) if value else None
            else:
                return self._memory_cache.get(key)
        except Exception:
            logger.debug("Cache get failed for key: %s", key, exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value in cache.

        Args:
            key: Cache key.
            value: Value to cache (must be JSON-serializable for Redis).
            ttl: Time-to-live in seconds (None = no expiry).
        """
        try:
            if self.settings.backend == "redis" and self._client:
                serialized = json.dumps(value, default=str)
                if ttl:
                    await self._client.setex(key, ttl, serialized)
                else:
                    await self._client.set(key, serialized)
            else:
                self._memory_cache[key] = value
        except Exception:
            logger.debug("Cache set failed for key: %s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        """Delete a value from cache.

        Args:
            key: Cache key to delete.
        """
        try:
            if self.settings.backend == "redis" and self._client:
                await self._client.delete(key)
            else:
                self._memory_cache.pop(key, None)
        except Exception:
            logger.debug("Cache delete failed for key: %s", key, exc_info=True)

    async def clear(self) -> None:
        """Clear all cached values."""
        try:
            if self.settings.backend == "redis" and self._client:
                await self._client.flushdb()
            else:
                self._memory_cache.clear()
        except Exception:
            logger.debug("Cache clear failed", exc_info=True)
