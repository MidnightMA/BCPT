"""Telethon message handling, conversion, sending, and history retrieval."""

from datetime import datetime, timezone
from typing import List, Optional

from telethon import TelegramClient
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageActionPinMessage,
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
    MessageService,
)

from app.core.constants import MessageType
from app.core.exceptions import MessageNotFoundError
from app.telegram.adapter import MessageDTO


def detect_message_type(msg: object) -> MessageType:
    """Detect whether message contains photo, document, video, audio, or text."""
    if isinstance(msg, MessageService):
        return MessageType.SERVICE
    media = getattr(msg, "media", None)
    if not media:
        return MessageType.TEXT
    if isinstance(media, MessageMediaPhoto):
        return MessageType.PHOTO
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if not doc:
            return MessageType.DOCUMENT
        attrs = getattr(doc, "attributes", [])
        for attr in attrs:
            if isinstance(attr, DocumentAttributeVideo):
                return MessageType.VIDEO
            if isinstance(attr, DocumentAttributeAudio):
                if getattr(attr, "voice", False):
                    return MessageType.VOICE
                return MessageType.AUDIO
        return MessageType.DOCUMENT
    return MessageType.UNSUPPORTED


def extract_media_meta(msg: object) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Extract filename, file size, and mime type from message media."""
    media = getattr(msg, "media", None)
    if not media:
        return None, None, None

    filename = None
    size = None
    mime_type = None

    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if doc:
            size = getattr(doc, "size", None)
            mime_type = getattr(doc, "mime_type", None)
            for attr in getattr(doc, "attributes", []):
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name
                    break
            # Fallback filenames if not explicitly tagged
            if not filename:
                for attr in getattr(doc, "attributes", []):
                    if isinstance(attr, DocumentAttributeVideo):
                        filename = "video.mp4"
                        break
                    if isinstance(attr, DocumentAttributeAudio):
                        filename = "voice.ogg" if getattr(attr, "voice", False) else "audio.mp3"
                        break
            if not filename:
                filename = "document.bin"
    elif isinstance(media, MessageMediaPhoto):
        filename = "photo.jpg"
        mime_type = "image/jpeg"

    return filename, size, mime_type


def telethon_message_to_dto(msg: object, chat_id: int) -> MessageDTO:
    """Map Telethon Message object to domain MessageDTO."""
    msg_id = getattr(msg, "id", 0)
    is_out = getattr(msg, "out", False)
    date = getattr(msg, "date", datetime.now(timezone.utc))

    sender_id = getattr(msg, "sender_id", None)
    sender = getattr(msg, "sender", None)
    sender_name = "You" if is_out else "Sender"
    if sender and not is_out:
        first = getattr(sender, "first_name", "") or ""
        last = getattr(sender, "last_name", "") or ""
        title = getattr(sender, "title", "") or ""
        sender_name = f"{first} {last}".strip() or title or f"User {sender_id}"

    # Text / Caption
    text = getattr(msg, "raw_text", "") or getattr(msg, "message", "") or ""
    media_type = detect_message_type(msg)
    media_filename, media_size, media_mime_type = extract_media_meta(msg)
    grouped_id = getattr(msg, "grouped_id", None)

    # Reply info
    reply_to = getattr(msg, "reply_to", None)
    reply_to_msg_id = getattr(reply_to, "reply_to_msg_id", None) if reply_to else None

    # Capabilities
    can_edit = bool(is_out and (text or media_type == MessageType.TEXT))
    can_delete = True

    return MessageDTO(
        id=msg_id,
        chat_id=chat_id,
        sender_id=sender_id,
        sender_name=sender_name,
        is_outgoing=is_out,
        text=text,
        date=date,
        reply_to_msg_id=reply_to_msg_id,
        reply_to_text=None,
        media_type=media_type,
        media_filename=media_filename,
        media_size=media_size,
        media_mime_type=media_mime_type,
        grouped_id=grouped_id,
        can_edit=can_edit,
        can_delete=can_delete,
    )


async def fetch_messages(
    client: TelegramClient,
    chat_id: int,
    limit: int = 10,
    offset_id: int = 0,
) -> List[MessageDTO]:
    """Fetch paginated message history for a chat."""
    entity = await client.get_input_entity(chat_id)
    raw_messages = await client.get_messages(
        entity,
        limit=limit,
        offset_id=offset_id,
    )
    # Reverse so older messages appear first in chat history view
    dtos = [telethon_message_to_dto(m, chat_id) for m in raw_messages]
    dtos.reverse()
    return dtos


async def send_text_message(
    client: TelegramClient,
    chat_id: int,
    text: str,
    reply_to_msg_id: Optional[int] = None,
) -> MessageDTO:
    """Send text message and return generated MessageDTO."""
    entity = await client.get_input_entity(chat_id)
    sent_msg = await client.send_message(
        entity,
        message=text,
        reply_to=reply_to_msg_id,
    )
    return telethon_message_to_dto(sent_msg, chat_id)


async def edit_text_message(
    client: TelegramClient,
    chat_id: int,
    message_id: int,
    text: str,
) -> MessageDTO:
    """Edit existing message text."""
    entity = await client.get_input_entity(chat_id)
    edited_msg = await client.edit_message(
        entity,
        message=message_id,
        text=text,
    )
    return telethon_message_to_dto(edited_msg, chat_id)


async def delete_messages(
    client: TelegramClient,
    chat_id: int,
    message_ids: List[int],
    revoke: bool = True,
) -> bool:
    """Delete messages in chat."""
    entity = await client.get_input_entity(chat_id)
    await client.delete_messages(entity, message_ids, revoke=revoke)
    return True


async def pin_message(
    client: TelegramClient,
    chat_id: int,
    message_id: int,
    notify: bool = False,
) -> bool:
    """Pin message in chat."""
    entity = await client.get_input_entity(chat_id)
    await client.pin_message(entity, message_id, notify=notify)
    return True


async def search_messages(
    client: TelegramClient,
    chat_id: int,
    query: str,
    limit: int = 10,
) -> List[MessageDTO]:
    """Search for messages containing the query string."""
    entity = await client.get_input_entity(chat_id)
    results = await client.get_messages(entity, search=query, limit=limit)
    return [telethon_message_to_dto(m, chat_id) for m in results]


async def fetch_single_message(
    client: TelegramClient,
    chat_id: int,
    message_id: int,
) -> MessageDTO:
    """Fetch an individual message by ID and convert to MessageDTO."""
    entity = await client.get_input_entity(chat_id)
    raw_msg = await client.get_messages(entity, ids=message_id)
    if not raw_msg:
        raise MessageNotFoundError(message_id=message_id)
    return telethon_message_to_dto(raw_msg, chat_id)


async def fetch_album_raw_messages(
    client: TelegramClient,
    entity: object,
    target_msg: object,
) -> List[object]:
    """Retrieve all raw Telethon message objects belonging to the same media group/album."""
    grouped_id = getattr(target_msg, "grouped_id", None)
    if not grouped_id:
        return [target_msg]

    target_id = getattr(target_msg, "id", 0)
    min_id = max(0, target_id - 15)
    max_id = target_id + 15

    surrounding = await client.get_messages(
        entity,
        limit=30,
        min_id=min_id,
        max_id=max_id,
    )
    album = [m for m in surrounding if getattr(m, "grouped_id", None) == grouped_id]
    if not any(getattr(m, "id", 0) == target_id for m in album):
        album.append(target_msg)

    album.sort(key=lambda m: getattr(m, "id", 0))
    return album
