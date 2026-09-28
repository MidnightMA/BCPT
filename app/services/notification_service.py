"""Notification dispatcher routing MTProto events to authorized bot users."""

from typing import Any, List, Optional

from telegram import Bot

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.repository import FavoriteRepository, UserRepository
from app.database.session import get_db_session
from app.telegram.adapter import MessageDTO
from app.utils.telegram_utils import escape_markdown, truncate_text

logger = get_logger(__name__)


class NotificationService:
    """Evaluates incoming Telethon message events and pushes alerts to authorized controllers."""

    def __init__(self, bot: Optional[Bot] = None) -> None:
        self.bot = bot
        self.settings = get_settings()

    def set_bot(self, bot: Bot) -> None:
        """Attach active python-telegram-bot instance."""
        self.bot = bot

    async def handle_new_message(self, msg: MessageDTO) -> None:
        """Process incoming message event and dispatch notifications if enabled."""
        if not self.bot:
            return

        authorized_users: List[int] = self.settings.AUTHORIZED_USER_IDS
        if not authorized_users:
            return

        async with get_db_session() as session:
            user_repo = UserRepository(session)
            fav_repo = FavoriteRepository(session)

            for user_id in authorized_users:
                user_settings = await user_repo.get_or_create_settings(user_id)

                if not user_settings.notifications_enabled:
                    continue

                if user_settings.notify_favorites_only:
                    is_fav = await fav_repo.is_favorite(user_id, msg.chat_id)
                    if not is_fav:
                        continue

                # Prepare notification text
                sender = escape_markdown(msg.sender_name)
                text_snippet = escape_markdown(truncate_text(msg.text or f"[{msg.media_type.value}]", max_length=150))
                alert_text = (
                    f"🔔 *New Message* \n"
                    f"👤 *From:* {sender}\n"
                    f"💬 *Chat ID:* {msg.chat_id}\n\n"
                    f"{text_snippet}"
                )

                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=alert_text,
                        parse_mode="Markdown",
                    )
                    logger.debug(f"Pushed notification for msg {msg.id} to user {user_id}")
                except Exception as send_err:
                    logger.warning(f"Failed to push notification to user {user_id}: {send_err}")
