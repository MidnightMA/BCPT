"""Message operations service covering history, pagination, sending, editing, and deleting."""

from typing import List, Optional

from app.core.exceptions import PermissionDeniedError
from app.core.logging import get_logger
from app.database.repository import AuditRepository
from app.database.session import get_db_session
from app.telegram.adapter import MediaItemDTO, MessageDTO, TelegramClientAdapter

logger = get_logger(__name__)


class MessageService:
    """Manages chat message history, sending text, editing, deleting, and pinning."""

    def __init__(self, adapter: TelegramClientAdapter) -> None:
        self.adapter = adapter

    async def get_messages(
        self,
        chat_id: int,
        limit: int = 10,
        offset_id: int = 0,
    ) -> List[MessageDTO]:
        """Fetch message history for a chat."""
        return await self.adapter.get_messages(
            chat_id=chat_id,
            limit=limit,
            offset_id=offset_id,
        )

    async def send_text_message(
        self,
        user_id: int,
        chat_id: int,
        text: str,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        """Send a plain text message after verifying sending permissions."""
        perms = await self.adapter.get_permissions(chat_id)
        if not perms.can_send_messages and not perms.can_post_messages:
            raise PermissionDeniedError(action="send text messages")

        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Message text cannot be empty.")

        dto = await self.adapter.send_message(
            chat_id=chat_id,
            text=clean_text,
            reply_to_msg_id=reply_to_msg_id,
        )

        async with get_db_session() as session:
            audit = AuditRepository(session)
            await audit.log_action(
                user_id=user_id,
                action="SEND_TEXT",
                chat_id=chat_id,
                details=f"msg_id={dto.id}, length={len(clean_text)}",
            )

        logger.info(f"User {user_id} sent message {dto.id} to chat {chat_id}")
        return dto

    async def edit_message(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        new_text: str,
    ) -> MessageDTO:
        """Edit message text after verifying editing rights."""
        perms = await self.adapter.get_permissions(chat_id)
        if not perms.can_edit_messages:
            raise PermissionDeniedError(action="edit messages")

        clean_text = new_text.strip()
        if not clean_text:
            raise ValueError("Edited message text cannot be empty.")

        dto = await self.adapter.edit_message(
            chat_id=chat_id,
            message_id=message_id,
            text=clean_text,
        )

        async with get_db_session() as session:
            audit = AuditRepository(session)
            await audit.log_action(
                user_id=user_id,
                action="EDIT_MESSAGE",
                chat_id=chat_id,
                details=f"msg_id={message_id}",
            )

        logger.info(f"User {user_id} edited message {message_id} in chat {chat_id}")
        return dto

    async def delete_message(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
    ) -> bool:
        """Delete message after verifying deletion rights."""
        perms = await self.adapter.get_permissions(chat_id)
        if not perms.can_delete_messages:
            raise PermissionDeniedError(action="delete messages")

        success = await self.adapter.delete_message(
            chat_id=chat_id,
            message_ids=[message_id],
            revoke=True,
        )

        async with get_db_session() as session:
            audit = AuditRepository(session)
            await audit.log_action(
                user_id=user_id,
                action="DELETE_MESSAGE",
                chat_id=chat_id,
                details=f"msg_id={message_id}",
            )

        logger.info(f"User {user_id} deleted message {message_id} in chat {chat_id}")
        return success

    async def pin_message(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        notify: bool = False,
    ) -> bool:
        """Pin a message after verifying pin rights."""
        perms = await self.adapter.get_permissions(chat_id)
        if not perms.can_pin_messages:
            raise PermissionDeniedError(action="pin messages")

        success = await self.adapter.pin_message(
            chat_id=chat_id,
            message_id=message_id,
            notify=notify,
        )

        async with get_db_session() as session:
            audit = AuditRepository(session)
            await audit.log_action(
                user_id=user_id,
                action="PIN_MESSAGE",
                chat_id=chat_id,
                details=f"msg_id={message_id}",
            )

        logger.info(f"User {user_id} pinned message {message_id} in chat {chat_id}")
        return success

    async def get_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> MessageDTO:
        """Fetch details for a single message."""
        return await self.adapter.get_message(chat_id, message_id)

    async def download_message_media(
        self,
        chat_id: int,
        message_id: int,
        temp_dir: str,
    ) -> List[MediaItemDTO]:
        """Download attached media items for message/album to temporary storage."""
        return await self.adapter.download_message_media(chat_id, message_id, temp_dir)
