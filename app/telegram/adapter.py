"""Data Transfer Objects (DTOs) and Telegram MTProto adapter implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.constants import ChatType, MessageType
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MediaItemDTO:
    """Represents a downloaded media item with local path and metadata."""
    file_path: Path
    media_type: MessageType
    filename: Optional[str] = None
    size: Optional[int] = None
    mime_type: Optional[str] = None
    caption: Optional[str] = None


@dataclass
class UserDTO:
    """Represents a Telegram user profile."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name


@dataclass
class ChatDTO:
    """Represents a Telegram chat, group, channel, or dialog."""
    id: int
    title: str
    chat_type: ChatType
    username: Optional[str] = None
    unread_count: int = 0
    participants_count: Optional[int] = None
    is_restricted: bool = False
    is_favorite: bool = False


@dataclass
class MessageDTO:
    """Represents an individual Telegram message."""
    id: int
    chat_id: int
    sender_id: Optional[int]
    sender_name: str
    is_outgoing: bool
    text: str
    date: datetime
    reply_to_msg_id: Optional[int] = None
    reply_to_text: Optional[str] = None
    media_type: MessageType = MessageType.TEXT
    media_filename: Optional[str] = None
    media_size: Optional[int] = None
    media_mime_type: Optional[str] = None
    grouped_id: Optional[int] = None
    can_edit: bool = False
    can_delete: bool = False


@dataclass
class ChatPermissionsDTO:
    """Evaluated capabilities and permissions for the controlled user account in a chat."""
    can_send_messages: bool = True
    can_send_media: bool = True
    can_post_messages: bool = True
    can_edit_messages: bool = True
    can_delete_messages: bool = True
    can_pin_messages: bool = True
    is_admin: bool = False
    is_creator: bool = False


class TelegramClientAdapter(ABC):
    """Abstract interface isolating Telethon MTProto calls from service logic."""

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    async def get_current_user(self) -> UserDTO:
        pass

    @abstractmethod
    async def get_dialogs(
        self,
        limit: int = 50,
        offset_date: Optional[datetime] = None,
        offset_id: int = 0,
    ) -> List[ChatDTO]:
        pass

    @abstractmethod
    async def get_chat(self, chat_id: int) -> ChatDTO:
        pass

    @abstractmethod
    async def get_messages(
        self,
        chat_id: int,
        limit: int = 10,
        offset_id: int = 0,
    ) -> List[MessageDTO]:
        pass

    @abstractmethod
    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        pass

    @abstractmethod
    async def send_file(
        self,
        chat_id: int,
        file_path: str,
        caption: Optional[str] = None,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        pass

    @abstractmethod
    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> MessageDTO:
        pass

    @abstractmethod
    async def delete_message(
        self,
        chat_id: int,
        message_ids: List[int],
        revoke: bool = True,
    ) -> bool:
        pass

    @abstractmethod
    async def pin_message(
        self,
        chat_id: int,
        message_id: int,
        notify: bool = False,
    ) -> bool:
        pass

    @abstractmethod
    async def get_permissions(self, chat_id: int) -> ChatPermissionsDTO:
        pass

    @abstractmethod
    async def search_messages(
        self,
        chat_id: int,
        query: str,
        limit: int = 10,
    ) -> List[MessageDTO]:
        pass

    @abstractmethod
    async def search_dialogs(
        self,
        query: str,
        limit: int = 20,
    ) -> List[ChatDTO]:
        pass

    @abstractmethod
    async def resolve_peer(self, identifier: str | int) -> ChatDTO:
        pass

    @abstractmethod
    async def join_channel(self, channel_id: int | str) -> ChatDTO:
        pass

    @abstractmethod
    async def get_message(self, chat_id: int, message_id: int) -> MessageDTO:
        pass

    @abstractmethod
    @abstractmethod
    async def download_message_media(
        self,
        chat_id: int,
        message_id: int,
        temp_dir: str,
    ) -> List[MediaItemDTO]:
        pass

    @abstractmethod
    async def mark_chat_read(
        self,
        chat_id: int,
        max_id: Optional[int] = None,
    ) -> None:
        pass


class TelethonAdapter(TelegramClientAdapter):
    """Concrete adapter connecting domain methods to Telethon functions with error mapping and throttling."""

    def __init__(
        self,
        client_manager: any,
        throttler: Optional[any] = None,
        cache_service: Optional[any] = None,
    ) -> None:
        self.manager = client_manager
        self._throttler = throttler
        self._cache_service = cache_service

    @property
    def throttler(self):
        if self._throttler is None:
            from app.telegram.limiter import get_telegram_throttler
            self._throttler = get_telegram_throttler()
        return self._throttler

    async def _get_cache(self):
        if self._cache_service is None:
            from app.cache.cache_service import get_cache_service
            self._cache_service = await get_cache_service()
        return self._cache_service

    async def connect(self) -> None:
        await self.manager.connect()

    async def disconnect(self) -> None:
        await self.manager.disconnect()

    def is_connected(self) -> bool:
        return self.manager.is_connected()

    async def get_current_user(self) -> UserDTO:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        settings = get_settings()
        try:
            client = await self.manager.ensure_connected()
            me = await self.throttler.execute(
                lambda: client.get_me(),
                dedup_key="current_user",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
            return UserDTO(
                id=getattr(me, "id", 0),
                first_name=getattr(me, "first_name", "") or "",
                last_name=getattr(me, "last_name", None),
                username=getattr(me, "username", None),
                phone=getattr(me, "phone", None),
            )
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_dialogs(
        self,
        limit: int = 50,
        offset_date: Optional[datetime] = None,
        offset_id: int = 0,
    ) -> List[ChatDTO]:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import fetch_dialogs
        settings = get_settings()
        try:
            cache = await self._get_cache()
            if offset_date is None:
                cached = await cache.get_cached_dialogs(limit=limit, offset_id=offset_id)
                if cached is not None:
                    return cached

            client = await self.manager.ensure_connected()
            dialogs = await self.throttler.execute(
                lambda: fetch_dialogs(
                    client,
                    limit=limit,
                    offset_date=offset_date,
                    offset_id=offset_id,
                ),
                dedup_key=f"dialogs:{limit}:{offset_id}",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
            if offset_date is None:
                await cache.set_cached_dialogs(limit=limit, offset_id=offset_id, dialogs=dialogs)
            return dialogs
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_chat(self, chat_id: int) -> ChatDTO:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import fetch_chat
        settings = get_settings()
        try:
            cache = await self._get_cache()
            cached = await cache.get_cached_chat(chat_id)
            if cached is not None:
                return cached

            client = await self.manager.ensure_connected()
            chat = await self.throttler.execute(
                lambda: fetch_chat(client, chat_id),
                chat_id=chat_id,
                dedup_key=f"chat:{chat_id}",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
            await cache.set_cached_chat(chat_id, chat)
            return chat
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_messages(
        self,
        chat_id: int,
        limit: int = 10,
        offset_id: int = 0,
    ) -> List[MessageDTO]:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import fetch_messages
        settings = get_settings()
        try:
            cache = await self._get_cache()
            cached = await cache.get_cached_messages(chat_id=chat_id, limit=limit, offset_id=offset_id)
            if cached is not None:
                return cached

            client = await self.manager.ensure_connected()
            messages = await self.throttler.execute(
                lambda: fetch_messages(
                    client,
                    chat_id=chat_id,
                    limit=limit,
                    offset_id=offset_id,
                ),
                chat_id=chat_id,
                dedup_key=f"msgs:{chat_id}:{limit}:{offset_id}",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
            await cache.set_cached_messages(chat_id=chat_id, limit=limit, offset_id=offset_id, messages=messages)
            return messages
        except Exception as exc:
            raise map_telethon_error(exc)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import send_text_message
        try:
            client = await self.manager.ensure_connected()
            msg = await self.throttler.execute(
                lambda: send_text_message(
                    client,
                    chat_id=chat_id,
                    text=text,
                    reply_to_msg_id=reply_to_msg_id,
                ),
                chat_id=chat_id,
            )
            cache = await self._get_cache()
            await cache.invalidate_chat(chat_id)
            await cache.invalidate_dialogs()
            return msg
        except Exception as exc:
            raise map_telethon_error(exc)

    async def send_file(
        self,
        chat_id: int,
        file_path: str,
        caption: Optional[str] = None,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.media import upload_file
        try:
            client = await self.manager.ensure_connected()
            msg = await self.throttler.execute(
                lambda: upload_file(
                    client,
                    chat_id=chat_id,
                    file_path=file_path,
                    caption=caption,
                    reply_to_msg_id=reply_to_msg_id,
                ),
                chat_id=chat_id,
                is_media=True,
            )
            cache = await self._get_cache()
            await cache.invalidate_chat(chat_id)
            await cache.invalidate_dialogs()
            return msg
        except Exception as exc:
            raise map_telethon_error(exc)

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> MessageDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import edit_text_message
        try:
            client = await self.manager.ensure_connected()
            msg = await self.throttler.execute(
                lambda: edit_text_message(
                    client,
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                ),
                chat_id=chat_id,
            )
            cache = await self._get_cache()
            await cache.invalidate_chat(chat_id)
            return msg
        except Exception as exc:
            raise map_telethon_error(exc)

    async def delete_message(
        self,
        chat_id: int,
        message_ids: List[int],
        revoke: bool = True,
    ) -> bool:
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import delete_messages
        try:
            client = await self.manager.ensure_connected()
            res = await self.throttler.execute(
                lambda: delete_messages(
                    client,
                    chat_id=chat_id,
                    message_ids=message_ids,
                    revoke=revoke,
                ),
                chat_id=chat_id,
            )
            cache = await self._get_cache()
            await cache.invalidate_chat(chat_id)
            return res
        except Exception as exc:
            raise map_telethon_error(exc)

    async def pin_message(
        self,
        chat_id: int,
        message_id: int,
        notify: bool = False,
    ) -> bool:
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import pin_message
        try:
            client = await self.manager.ensure_connected()
            res = await self.throttler.execute(
                lambda: pin_message(
                    client,
                    chat_id=chat_id,
                    message_id=message_id,
                    notify=notify,
                ),
                chat_id=chat_id,
            )
            cache = await self._get_cache()
            await cache.invalidate_chat(chat_id)
            return res
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_permissions(self, chat_id: int) -> ChatPermissionsDTO:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        from app.telegram.permissions import evaluate_permissions
        settings = get_settings()
        try:
            cache = await self._get_cache()
            cached = await cache.get_cached_permissions(chat_id)
            if cached is not None:
                return cached

            client = await self.manager.ensure_connected()
            perms = await self.throttler.execute(
                lambda: evaluate_permissions(client, chat_id),
                chat_id=chat_id,
                dedup_key=f"perm:{chat_id}",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
            await cache.set_cached_permissions(chat_id, perms)
            return perms
        except Exception as exc:
            raise map_telethon_error(exc)

    async def search_messages(
        self,
        chat_id: int,
        query: str,
        limit: int = 10,
    ) -> List[MessageDTO]:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import search_messages
        settings = get_settings()
        try:
            client = await self.manager.ensure_connected()
            return await self.throttler.execute(
                lambda: search_messages(client, chat_id, query, limit),
                chat_id=chat_id,
                dedup_key=f"smsgs:{chat_id}:{query}:{limit}",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
        except Exception as exc:
            raise map_telethon_error(exc)

    async def search_dialogs(
        self,
        query: str,
        limit: int = 20,
    ) -> List[ChatDTO]:
        all_dialogs = await self.get_dialogs(limit=100)
        q = query.lower()
        matched = [
            d for d in all_dialogs
            if q in d.title.lower() or (d.username and q in d.username.lower())
        ]
        return matched[:limit]

    async def resolve_peer(self, identifier: str | int) -> ChatDTO:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import resolve_peer_entity
        settings = get_settings()
        try:
            cache = await self._get_cache()
            cached = await cache.get_cached_peer(identifier)
            if cached is not None:
                return cached

            client = await self.manager.ensure_connected()
            chat = await self.throttler.execute(
                lambda: resolve_peer_entity(client, identifier),
                dedup_key=f"peer:{identifier}",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
            await cache.set_cached_peer(identifier, chat)
            await cache.set_cached_chat(chat.id, chat)
            return chat
        except Exception as exc:
            raise map_telethon_error(exc)

    async def join_channel(self, channel_id: int | str) -> ChatDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import join_channel_entity
        try:
            client = await self.manager.ensure_connected()
            chat = await self.throttler.execute(
                lambda: join_channel_entity(client, channel_id),
                dedup_key=f"join:{channel_id}",
            )
            cache = await self._get_cache()
            await cache.invalidate_dialogs()
            await cache.set_cached_chat(chat.id, chat)
            return chat
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_message(self, chat_id: int, message_id: int) -> MessageDTO:
        from app.core.config import get_settings
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import fetch_single_message
        settings = get_settings()
        try:
            cache = await self._get_cache()
            cached = await cache.get_cached_single_message(chat_id, message_id)
            if cached is not None:
                return cached

            client = await self.manager.ensure_connected()
            msg = await self.throttler.execute(
                lambda: fetch_single_message(client, chat_id, message_id),
                chat_id=chat_id,
                dedup_key=f"msg:{chat_id}:{message_id}",
                debounce_window=settings.TELEGRAM_DEDUPLICATION_WINDOW,
            )
            await cache.set_cached_single_message(chat_id, message_id, msg)
            return msg
        except Exception as exc:
            raise map_telethon_error(exc)

    async def download_message_media(
        self,
        chat_id: int,
        message_id: int,
        temp_dir: str,
    ) -> List[MediaItemDTO]:
        from app.telegram.client import map_telethon_error
        from app.telegram.media import download_media_for_message
        try:
            client = await self.manager.ensure_connected()
            return await self.throttler.execute(
                lambda: download_media_for_message(
                    client,
                    chat_id=chat_id,
                    message_id=message_id,
                    temp_dir=temp_dir,
                ),
                chat_id=chat_id,
                is_media=True,
            )
        except Exception as exc:
            raise map_telethon_error(exc)

    async def mark_chat_read(
        self,
        chat_id: int,
        max_id: Optional[int] = None,
    ) -> None:
        """Acknowledge messages as read in chat only when explicitly opened in panel."""
        from app.core.config import get_settings
        settings = get_settings()
        if not settings.TELEGRAM_AUTO_READ_ON_INSPECT:
            return
        try:
            client = await self.manager.ensure_connected()
            entity = await client.get_input_entity(chat_id)
            await self.throttler.execute(
                lambda: client.send_read_acknowledge(entity, max_id=max_id),
                chat_id=chat_id,
            )
        except Exception as exc:
            logger.debug(f"Failed to acknowledge read for chat {chat_id}: {exc}")



_adapter_instance: Optional[TelegramClientAdapter] = None


def get_telegram_adapter() -> TelegramClientAdapter:
    """Return singleton Telegram adapter."""
    global _adapter_instance
    if _adapter_instance is None:
        from app.telegram.client import get_client_manager
        manager = get_client_manager()
        _adapter_instance = TelethonAdapter(manager)
    return _adapter_instance
