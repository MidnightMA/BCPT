"""High-level application caching operations for dialogs, permissions, and query results."""

import json
from typing import Any, Optional

from app.cache.redis import CacheClient, get_cache
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """Provides strongly-typed serialization and prefixing for cached entities."""

    def __init__(self, cache_client: CacheClient) -> None:
        self.cache = cache_client

    async def get_json(self, key: str) -> Optional[Any]:
        """Fetch and deserialize JSON from cache."""
        val = await self.cache.get(key)
        if not val:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, ttl: Optional[int] = 300) -> bool:
        """Serialize and store an object as JSON in cache."""
        try:
            payload = json.dumps(value, default=str)
            return await self.cache.set(key, payload, ttl=ttl)
        except Exception as exc:
            logger.warning(f"Failed to serialize value for cache key '{key}': {exc}")
            return False

    async def delete(self, key: str) -> bool:
        return await self.cache.delete(key)

    # Specific domain caching helpers
    async def get_cached_chat(self, chat_id: int) -> Optional[dict]:
        return await self.get_json(f"tg:chat:{chat_id}")

    async def set_cached_chat(self, chat_id: int, chat_data: dict, ttl: int = 600) -> bool:
        return await self.set_json(f"tg:chat:{chat_id}", chat_data, ttl=ttl)

    async def get_cached_permissions(self, chat_id: int) -> Optional[dict]:
        return await self.get_json(f"tg:perm:{chat_id}")

    async def set_cached_permissions(self, chat_id: int, perms_data: dict, ttl: int = 300) -> bool:
        return await self.set_json(f"tg:perm:{chat_id}", perms_data, ttl=ttl)

    async def invalidate_chat(self, chat_id: int) -> None:
        await self.delete(f"tg:chat:{chat_id}")
        await self.delete(f"tg:perm:{chat_id}")


async def get_cache_service() -> CacheService:
    """Factory for CacheService."""
    cache = await get_cache()
    return CacheService(cache)
