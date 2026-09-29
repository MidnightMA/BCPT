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
    async def download_message_media(
        self,
        chat_id: int,
        message_id: int,
        temp_dir: str,
    ) -> List[MediaItemDTO]:
        pass


class TelethonAdapter(TelegramClientAdapter):
    """Concrete adapter connecting domain methods to Telethon functions with error mapping."""

    def __init__(self, client_manager: any) -> None:
        self.manager = client_manager

    async def connect(self) -> None:
        await self.manager.connect()

    async def disconnect(self) -> None:
        await self.manager.disconnect()

    def is_connected(self) -> bool:
        return self.manager.is_connected()

    async def get_current_user(self) -> UserDTO:
        from app.telegram.client import map_telethon_error
        try:
            client = self.manager.raw_client
            me = await client.get_me()
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
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import fetch_dialogs
        try:
            return await fetch_dialogs(
                self.manager.raw_client,
                limit=limit,
                offset_date=offset_date,
                offset_id=offset_id,
            )
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_chat(self, chat_id: int) -> ChatDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import fetch_chat
        try:
            return await fetch_chat(self.manager.raw_client, chat_id)
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_messages(
        self,
        chat_id: int,
        limit: int = 10,
        offset_id: int = 0,
    ) -> List[MessageDTO]:
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import fetch_messages
        try:
            return await fetch_messages(
                self.manager.raw_client,
                chat_id=chat_id,
                limit=limit,
                offset_id=offset_id,
            )
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
            return await send_text_message(
                self.manager.raw_client,
                chat_id=chat_id,
                text=text,
                reply_to_msg_id=reply_to_msg_id,
            )
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
            return await upload_file(
                self.manager.raw_client,
                chat_id=chat_id,
                file_path=file_path,
                caption=caption,
                reply_to_msg_id=reply_to_msg_id,
            )
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
            return await edit_text_message(
                self.manager.raw_client,
                chat_id=chat_id,
                message_id=message_id,
                text=text,
            )
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
            return await delete_messages(
                self.manager.raw_client,
                chat_id=chat_id,
                message_ids=message_ids,
                revoke=revoke,
            )
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
            return await pin_message(
                self.manager.raw_client,
                chat_id=chat_id,
                message_id=message_id,
                notify=notify,
            )
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_permissions(self, chat_id: int) -> ChatPermissionsDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.permissions import evaluate_permissions
        try:
            return await evaluate_permissions(self.manager.raw_client, chat_id)
        except Exception as exc:
            raise map_telethon_error(exc)

    async def search_messages(
        self,
        chat_id: int,
        query: str,
        limit: int = 10,
    ) -> List[MessageDTO]:
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import search_messages
        try:
            return await search_messages(self.manager.raw_client, chat_id, query, limit)
        except Exception as exc:
            raise map_telethon_error(exc)

    async def search_dialogs(
        self,
        query: str,
        limit: int = 20,
    ) -> List[ChatDTO]:
        # Filter retrieved dialogs by query
        all_dialogs = await self.get_dialogs(limit=100)
        q = query.lower()
        matched = [
            d for d in all_dialogs
            if q in d.title.lower() or (d.username and q in d.username.lower())
        ]
        return matched[:limit]

    async def resolve_peer(self, identifier: str | int) -> ChatDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import resolve_peer_entity
        try:
            return await resolve_peer_entity(self.manager.raw_client, identifier)
        except Exception as exc:
            raise map_telethon_error(exc)

    async def join_channel(self, channel_id: int | str) -> ChatDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.dialogs import join_channel_entity
        try:
            return await join_channel_entity(self.manager.raw_client, channel_id)
        except Exception as exc:
            raise map_telethon_error(exc)

    async def get_message(self, chat_id: int, message_id: int) -> MessageDTO:
        from app.telegram.client import map_telethon_error
        from app.telegram.messages import fetch_single_message
        try:
            return await fetch_single_message(self.manager.raw_client, chat_id, message_id)
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
            return await download_media_for_message(
                self.manager.raw_client,
                chat_id=chat_id,
                message_id=message_id,
                temp_dir=temp_dir,
            )
        except Exception as exc:
            raise map_telethon_error(exc)


_adapter_instance: Optional[TelegramClientAdapter] = None


def get_telegram_adapter() -> TelegramClientAdapter:
    """Return singleton Telegram adapter."""
    global _adapter_instance
    if _adapter_instance is None:
        from app.telegram.client import get_client_manager
        manager = get_client_manager()
        _adapter_instance = TelethonAdapter(manager)
    return _adapter_instance
