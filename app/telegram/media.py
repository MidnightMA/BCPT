"""Telethon media handling, file uploads, and downloads."""

from pathlib import Path
from typing import Optional

from telethon import TelegramClient

from app.core.exceptions import MediaProcessingError
from app.core.logging import get_logger
from app.telegram.adapter import MessageDTO
from app.telegram.messages import telethon_message_to_dto

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
