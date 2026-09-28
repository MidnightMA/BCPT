"""Permission check and capability enforcement service."""

from app.core.exceptions import PermissionDeniedError
from app.core.logging import get_logger
from app.telegram.adapter import ChatPermissionsDTO, TelegramClientAdapter

logger = get_logger(__name__)


class PermissionService:
    """Service to evaluate and enforce account capabilities in chats."""

    def __init__(self, adapter: TelegramClientAdapter) -> None:
        self.adapter = adapter

    async def get_permissions(self, chat_id: int) -> ChatPermissionsDTO:
        """Fetch granular permissions for the user account in chat."""
        return await self.adapter.get_permissions(chat_id)

    async def ensure_can_send(self, chat_id: int) -> None:
        """Validate sending permissions; raises PermissionDeniedError if forbidden."""
        perms = await self.get_permissions(chat_id)
        if not perms.can_send_messages and not perms.can_post_messages:
            raise PermissionDeniedError(action="send messages")

    async def ensure_can_send_media(self, chat_id: int) -> None:
        """Validate media upload permissions; raises PermissionDeniedError if forbidden."""
        perms = await self.get_permissions(chat_id)
        if not perms.can_send_media and not perms.can_post_messages:
            raise PermissionDeniedError(action="send media files")

    async def ensure_can_delete(self, chat_id: int) -> None:
        """Validate message deletion permissions; raises PermissionDeniedError if forbidden."""
        perms = await self.get_permissions(chat_id)
        if not perms.can_delete_messages:
            raise PermissionDeniedError(action="delete messages")

    async def ensure_can_pin(self, chat_id: int) -> None:
        """Validate message pin permissions; raises PermissionDeniedError if forbidden."""
        perms = await self.get_permissions(chat_id)
        if not perms.can_pin_messages:
            raise PermissionDeniedError(action="pin messages")
