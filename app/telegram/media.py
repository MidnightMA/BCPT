"""Telethon media handling, file uploads, and downloads."""

from pathlib import Path
from typing import List, Optional

from telethon import TelegramClient

from app.core.constants import MAX_UPLOAD_SIZE_BYTES, MessageType
from app.core.exceptions import MediaProcessingError, MessageNotFoundError
from app.core.logging import get_logger
from app.core.security import generate_safe_temp_path
from app.telegram.adapter import MediaItemDTO, MessageDTO
from app.telegram.messages import (
    detect_message_type,
    extract_media_meta,
    fetch_album_raw_messages,
    telethon_message_to_dto,
)

logger = get_logger(__name__)


async def upload_file(
    client: TelegramClient,
    chat_id: int,
    file_path: str | Path,
    caption: Optional[str] = None,
    reply_to_msg_id: Optional[int] = None,
) -> MessageDTO:
    """Upload a local file via Telethon to the target chat."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise MediaProcessingError(f"Local file does not exist: {file_path}")

    logger.info(f"Uploading file '{path.name}' ({path.stat().st_size} bytes) to chat_id={chat_id}")

    try:
        entity = await client.get_input_entity(chat_id)
        sent_msg = await client.send_file(
            entity,
            file=str(path),
            caption=caption,
            reply_to=reply_to_msg_id,
        )
        return telethon_message_to_dto(sent_msg, chat_id)
    except Exception as exc:
        logger.error(f"Error uploading media file to chat {chat_id}: {exc}", exc_info=True)
        raise MediaProcessingError(f"Failed to upload media to Telegram: {exc}") from exc


async def download_media_for_message(
    client: TelegramClient,
    chat_id: int,
    message_id: int,
    temp_dir: str,
) -> List[MediaItemDTO]:
    """Download all media attached to a message or album into safe temp directory."""
    entity = await client.get_input_entity(chat_id)
    raw_msg = await client.get_messages(entity, ids=message_id)
    if not raw_msg:
        raise MessageNotFoundError(message_id=message_id)

    album_msgs = await fetch_album_raw_messages(client, entity, raw_msg)
    media_items: List[MediaItemDTO] = []

    for msg in album_msgs:
        media = getattr(msg, "media", None)
        if not media:
            continue

        media_type = detect_message_type(msg)
        if media_type in (MessageType.TEXT, MessageType.SERVICE):
            continue

        filename, size, mime_type = extract_media_meta(msg)
        caption = getattr(msg, "raw_text", "") or getattr(msg, "message", "") or ""

        if size and size > MAX_UPLOAD_SIZE_BYTES:
            logger.warning(
                f"Skipping download for msg {getattr(msg, 'id', 0)}: size {size} bytes exceeds limit of {MAX_UPLOAD_SIZE_BYTES} bytes."
            )
            continue

        safe_path = generate_safe_temp_path(filename or "media.bin", temp_dir)
        try:
            downloaded = await client.download_media(message=msg, file=str(safe_path))
            if downloaded and Path(downloaded).is_file():
                p = Path(downloaded)
                media_items.append(
                    MediaItemDTO(
                        file_path=p,
                        media_type=media_type,
                        filename=filename or p.name,
                        size=p.stat().st_size,
                        mime_type=mime_type,
                        caption=caption if caption else None,
                    )
                )
        except Exception as exc:
            logger.error(f"Failed to download media for message {getattr(msg, 'id', 0)}: {exc}", exc_info=True)

    return media_items
