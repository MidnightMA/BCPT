"""Media processing and file upload service with guaranteed disk cleanup."""

from pathlib import Path
from typing import Optional

from app.core.exceptions import PermissionDeniedError
from app.core.logging import get_logger
from app.database.repository import AuditRepository
from app.database.session import get_db_session
from app.telegram.adapter import MessageDTO, TelegramClientAdapter
from app.utils.cleanup import safe_remove_file

logger = get_logger(__name__)


class MediaService:
    """Manages file verification, upload to Telethon, and guaranteed disk cleanup."""

    def __init__(self, adapter: TelegramClientAdapter) -> None:
        self.adapter = adapter

    async def send_file(
        self,
        user_id: int,
        chat_id: int,
        temp_file_path: str | Path,
        caption: Optional[str] = None,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        """Upload file via Telethon and guarantee local file cleanup in finally block."""
        perms = await self.adapter.get_permissions(chat_id)
        if not perms.can_send_media and not perms.can_post_messages:
            safe_remove_file(temp_file_path)
            raise PermissionDeniedError(action="send media/files")

        try:
            dto = await self.adapter.send_file(
                chat_id=chat_id,
                file_path=str(temp_file_path),
                caption=caption,
                reply_to_msg_id=reply_to_msg_id,
            )

            async with get_db_session() as session:
                audit = AuditRepository(session)
                await audit.log_action(
                    user_id=user_id,
                    action="SEND_FILE",
                    chat_id=chat_id,
                    details=f"msg_id={dto.id}, filename={dto.media_filename}",
                )

            logger.info(f"User {user_id} uploaded file to chat {chat_id} (msg_id={dto.id})")
            return dto

        finally:
            # Guarantee cleanup of temporary disk storage
            safe_remove_file(temp_file_path)
