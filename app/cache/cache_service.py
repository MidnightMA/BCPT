"""High-level application caching operations for dialogs, permissions, messages, and peers."""

from dataclasses import asdict
from datetime import datetime
import json
from typing import Any, List, Optional

from app.cache.redis import CacheClient, get_cache
from app.core.config import get_settings
from app.core.constants import ChatType, MessageType
from app.core.logging import get_logger
from app.telegram.adapter import ChatDTO, ChatPermissionsDTO, MessageDTO

logger = get_logger(__name__)


def _chat_dto_to_dict(dto: ChatDTO) -> dict:
    return {
        "id": dto.id,
        "title": dto.title,
        "chat_type": dto.chat_type.value,
        "username": dto.username,
        "unread_count": dto.unread_count,
        "participants_count": dto.participants_count,
        "is_restricted": dto.is_restricted,
        "is_favorite": dto.is_favorite,
    }


def _dict_to_chat_dto(d: dict) -> ChatDTO:
    return ChatDTO(
        id=int(d["id"]),
        title=d.get("title", "Unnamed Chat"),
        chat_type=ChatType(d.get("chat_type", "group")),
        username=d.get("username"),
        unread_count=int(d.get("unread_count", 0)),
        participants_count=d.get("participants_count"),
        is_restricted=bool(d.get("is_restricted", False)),
        is_favorite=bool(d.get("is_favorite", False)),
    )


def _message_dto_to_dict(dto: MessageDTO) -> dict:
    return {
        "id": dto.id,
        "chat_id": dto.chat_id,
        "sender_id": dto.sender_id,
        "sender_name": dto.sender_name,
        "is_outgoing": dto.is_outgoing,
        "text": dto.text,
        "date": dto.date.isoformat(),
        "reply_to_msg_id": dto.reply_to_msg_id,
        "reply_to_text": dto.reply_to_text,
        "media_type": dto.media_type.value,
        "media_filename": dto.media_filename,
        "media_size": dto.media_size,
        "media_mime_type": dto.media_mime_type,
        "grouped_id": dto.grouped_id,
        "can_edit": dto.can_edit,
        "can_delete": dto.can_delete,
    }


def _dict_to_message_dto(d: dict) -> MessageDTO:
    date_val = d.get("date")
    if isinstance(date_val, str):
        try:
            parsed_date = datetime.fromisoformat(date_val)
        except Exception:
            parsed_date = datetime.now()
    else:
        parsed_date = datetime.now()

    return MessageDTO(
        id=int(d["id"]),
        chat_id=int(d["chat_id"]),
        sender_id=d.get("sender_id"),
        sender_name=d.get("sender_name", ""),
        is_outgoing=bool(d.get("is_outgoing", False)),
        text=d.get("text", ""),
        date=parsed_date,
        reply_to_msg_id=d.get("reply_to_msg_id"),
        reply_to_text=d.get("reply_to_text"),
        media_type=MessageType(d.get("media_type", "text")),
        media_filename=d.get("media_filename"),
        media_size=d.get("media_size"),
        media_mime_type=d.get("media_mime_type"),
        grouped_id=d.get("grouped_id"),
        can_edit=bool(d.get("can_edit", False)),
        can_delete=bool(d.get("can_delete", False)),
    )


def _perms_dto_to_dict(dto: ChatPermissionsDTO) -> dict:
    return asdict(dto)


def _dict_to_perms_dto(d: dict) -> ChatPermissionsDTO:
    return ChatPermissionsDTO(**d)


class CacheService:
    """Provides strongly-typed serialization and prefixing for cached entities."""

    def __init__(self, cache_client: CacheClient) -> None:
        self.cache = cache_client
        self.settings = get_settings()

    async def get_json(self, key: str) -> Optional[Any]:
        """Fetch and deserialize JSON from cache."""
        val = await self.cache.get(key)
        if not val:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
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

    # 1. Chat metadata caching
    async def get_cached_chat(self, chat_id: int) -> Optional[ChatDTO]:
        data = await self.get_json(f"tg:chat:{chat_id}")
        if data and isinstance(data, dict):
            return _dict_to_chat_dto(data)
        return None

    async def set_cached_chat(self, chat_id: int, chat: ChatDTO, ttl: Optional[int] = None) -> bool:
        effective_ttl = ttl if ttl is not None else self.settings.TELEGRAM_CACHE_TTL_CHATS
        return await self.set_json(f"tg:chat:{chat_id}", _chat_dto_to_dict(chat), ttl=effective_ttl)

    # 2. Peer / Entity resolution caching
    async def get_cached_peer(self, identifier: str | int) -> Optional[ChatDTO]:
        norm = str(identifier).strip().lower().lstrip("@")
        data = await self.get_json(f"tg:peer:{norm}")
        if data and isinstance(data, dict):
            return _dict_to_chat_dto(data)
        return None

    async def set_cached_peer(self, identifier: str | int, chat: ChatDTO, ttl: Optional[int] = None) -> bool:
        norm = str(identifier).strip().lower().lstrip("@")
        effective_ttl = ttl if ttl is not None else self.settings.TELEGRAM_CACHE_TTL_PEERS
        return await self.set_json(f"tg:peer:{norm}", _chat_dto_to_dict(chat), ttl=effective_ttl)

    # 3. Permissions caching
    async def get_cached_permissions(self, chat_id: int) -> Optional[ChatPermissionsDTO]:
        data = await self.get_json(f"tg:perm:{chat_id}")
        if data and isinstance(data, dict):
            return _dict_to_perms_dto(data)
        return None

    async def set_cached_permissions(self, chat_id: int, perms: ChatPermissionsDTO, ttl: Optional[int] = None) -> bool:
        effective_ttl = ttl if ttl is not None else self.settings.TELEGRAM_CACHE_TTL_PERMISSIONS
        return await self.set_json(f"tg:perm:{chat_id}", _perms_dto_to_dict(perms), ttl=effective_ttl)

    # 4. Dialogs list caching
    async def get_cached_dialogs(self, limit: int, offset_id: int = 0) -> Optional[List[ChatDTO]]:
        data = await self.get_json(f"tg:dialogs:{limit}:{offset_id}")
        if data and isinstance(data, list):
            return [_dict_to_chat_dto(item) for item in data]
        return None

    async def set_cached_dialogs(
        self,
        limit: int,
        offset_id: int,
        dialogs: List[ChatDTO],
        ttl: Optional[int] = None,
    ) -> bool:
        effective_ttl = ttl if ttl is not None else self.settings.TELEGRAM_CACHE_TTL_DIALOGS
        serialized = [_chat_dto_to_dict(d) for d in dialogs]
        return await self.set_json(f"tg:dialogs:{limit}:{offset_id}", serialized, ttl=effective_ttl)

    # 5. Message history caching
    async def get_cached_messages(self, chat_id: int, limit: int, offset_id: int = 0) -> Optional[List[MessageDTO]]:
        data = await self.get_json(f"tg:msgs:{chat_id}:{limit}:{offset_id}")
        if data and isinstance(data, list):
            return [_dict_to_message_dto(item) for item in data]
        return None

    async def set_cached_messages(
        self,
        chat_id: int,
        limit: int,
        offset_id: int,
        messages: List[MessageDTO],
        ttl: Optional[int] = None,
    ) -> bool:
        effective_ttl = ttl if ttl is not None else self.settings.TELEGRAM_CACHE_TTL_MESSAGES
        serialized = [_message_dto_to_dict(m) for m in messages]
        return await self.set_json(f"tg:msgs:{chat_id}:{limit}:{offset_id}", serialized, ttl=effective_ttl)

    # 6. Single message caching
    async def get_cached_single_message(self, chat_id: int, message_id: int) -> Optional[MessageDTO]:
        data = await self.get_json(f"tg:msg:{chat_id}:{message_id}")
        if data and isinstance(data, dict):
            return _dict_to_message_dto(data)
        return None

    async def set_cached_single_message(
        self,
        chat_id: int,
        message_id: int,
        message: MessageDTO,
        ttl: Optional[int] = None,
    ) -> bool:
        effective_ttl = ttl if ttl is not None else self.settings.TELEGRAM_CACHE_TTL_MESSAGES
        return await self.set_json(f"tg:msg:{chat_id}:{message_id}", _message_dto_to_dict(message), ttl=effective_ttl)

    # Invalidation
    async def invalidate_chat(self, chat_id: int) -> None:
        """Invalidate all cached entities for a chat."""
        await self.delete(f"tg:chat:{chat_id}")
        await self.delete(f"tg:perm:{chat_id}")
        # Note: In-memory cache handles exact key deletion.

    async def invalidate_dialogs(self) -> None:
        """Invalidate dialog listings."""
        await self.delete("tg:dialogs:50:0")
        await self.delete("tg:dialogs:100:0")


async def get_cache_service() -> CacheService:
    """Factory for CacheService."""
    cache = await get_cache()
    return CacheService(cache)
