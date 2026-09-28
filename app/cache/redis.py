"""Redis connection manager with automatic in-memory fallback."""

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class InMemoryCache:
    """Thread-safe and async-compatible in-memory fallback cache with TTL expiration."""

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            if key not in self._store:
                return None
            val, expiry = self._store[key]
            if expiry is not None and time.monotonic() > expiry:
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        async with self._lock:
            expiry = time.monotonic() + ttl if ttl else None
            self._store[key] = (value, expiry)
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._store.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        val = await self.get(key)
        return val is not None

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class CacheClient:
    """High-level async cache client wrapping Redis with automatic in-memory fallback."""

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._memory = InMemoryCache()
        self._is_redis_available = False

    async def initialize(self) -> None:
        """Attempt connection to Redis if configured; fallback to memory on failure."""
        if not self.redis_url:
            logger.info("No REDIS_URL configured; using in-memory cache fallback.")
            self._is_redis_available = False
            return

        try:
            client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            await client.ping()
            self._redis = client
            self._is_redis_available = True
            logger.info("Connected successfully to Redis cache.")
        except Exception as exc:
            logger.warning(
                f"Could not connect to Redis at {self.redis_url}: {exc}. "
                "Defaulting to in-memory cache fallback."
            )
            self._is_redis_available = False
            self._redis = None

    @property
    def is_redis_available(self) -> bool:
        return self._is_redis_available

    async def get(self, key: str) -> Optional[str]:
        if self._is_redis_available and self._redis:
            try:
                return await self._redis.get(key)
            except Exception as exc:
                logger.warning(f"Redis get failed for key '{key}': {exc}. Trying memory.")
        return await self._memory.get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        if self._is_redis_available and self._redis:
            try:
                if ttl:
                    await self._redis.setex(key, ttl, value)
                else:
                    await self._redis.set(key, value)
                return True
            except Exception as exc:
                logger.warning(f"Redis set failed for key '{key}': {exc}. Using memory.")
        return await self._memory.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        deleted = False
        if self._is_redis_available and self._redis:
            try:
                deleted = bool(await self._redis.delete(key))
            except Exception as exc:
                logger.warning(f"Redis delete failed for key '{key}': {exc}.")
        mem_deleted = await self._memory.delete(key)
        return deleted or mem_deleted

    async def exists(self, key: str) -> bool:
        if self._is_redis_available and self._redis:
            try:
                return bool(await self._redis.exists(key))
            except Exception as exc:
                logger.warning(f"Redis exists failed for key '{key}': {exc}.")
        return await self._memory.exists(key)

    async def close(self) -> None:
        """Close Redis connection pool if active."""
        if self._redis:
            try:
                await self._redis.close()
                logger.info("Closed Redis cache connection.")
            except Exception:
                pass
        self._redis = None
        self._is_redis_available = False


_cache_instance: Optional[CacheClient] = None


async def get_cache() -> CacheClient:
    """Return initialized global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        settings = get_settings()
        _cache_instance = CacheClient(settings.REDIS_URL)
        await _cache_instance.initialize()
    return _cache_instance


async def close_cache() -> None:
    """Close global cache instance."""
    global _cache_instance
    if _cache_instance is not None:
        await _cache_instance.close()
        _cache_instance = None
