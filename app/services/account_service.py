"""Account and connection status service."""

from typing import Any, Dict, Optional

from app.core.exceptions import ConnectionFailedError
from app.core.logging import get_logger
from app.telegram.adapter import TelegramClientAdapter, UserDTO

logger = get_logger(__name__)


class AccountService:
    """Provides high-level profile, connection health, and account diagnostics."""

    def __init__(self, adapter: TelegramClientAdapter) -> None:
        self.adapter = adapter

    def is_connected(self) -> bool:
        """Check if Telethon MTProto client is connected."""
        return self.adapter.is_connected()

    async def get_current_user(self) -> Optional[UserDTO]:
        """Return the UserDTO of the authenticated user account, or None if unavailable."""
        try:
            if not self.is_connected():
                return None
            return await self.adapter.get_current_user()
        except Exception as exc:
            logger.warning(f"Could not retrieve current user profile: {exc}")
            return None

    async def get_account_summary(self) -> Dict[str, Any]:
        """Generate a summary dictionary describing current account status."""
        connected = self.is_connected()
        user: Optional[UserDTO] = None
        if connected:
            try:
                user = await self.get_current_user()
            except Exception:
                connected = False

        return {
            "is_connected": connected,
            "user_id": user.id if user else None,
            "name": user.full_name if user else "Disconnected",
            "username": user.username if user else None,
            "phone": user.phone if user else None,
        }
