"""Handlers for viewing and updating user settings and preferences."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards.settings import get_settings_keyboard
from app.core.logging import get_logger
from app.database.repository import UserRepository
from app.database.session import get_db_session

logger = get_logger(__name__)


async def render_settings_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render user settings dashboard."""
    user = update.effective_user
    if not user:
        return

    async with get_db_session() as session:
        user_repo = UserRepository(session)
        settings = await user_repo.get_or_create_settings(user.id)

        text = (
            "⚙️ *Control Panel Settings* \n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Configure how the control bot handles alerts and account synchronization:\n\n"
            f"• *Push Notifications:* {'Enabled 🔔' if settings.notifications_enabled else 'Muted 🔕'}\n"
            f"• *Alert Scope:* {'⭐ Favorites Only' if settings.notify_favorites_only else '🌐 All Chats'}\n"
            f"• *Auto-Refresh:* {'Enabled ⚡' if settings.auto_refresh else 'Disabled ⏸'}\n\n"
            " _Click any button below to toggle that setting:_ "
        )
        keyboard = get_settings_keyboard(settings)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as exc:
            if "Message is not modified" not in str(exc):
                logger.debug(f"Failed to edit settings: {exc}")
    elif update.effective_message:
        await update.effective_message.reply_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def handle_toggle_setting(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    setting_key: str,
) -> None:
    """Toggle a specific setting and refresh settings menu."""
    user = update.effective_user
    if not user:
        return

    async with get_db_session() as session:
        user_repo = UserRepository(session)
        current = await user_repo.get_or_create_settings(user.id)

        if setting_key == "notif":
            await user_repo.update_settings(user.id, notifications_enabled=not current.notifications_enabled)
        elif setting_key == "fav_only":
            await user_repo.update_settings(user.id, notify_favorites_only=not current.notify_favorites_only)
        elif setting_key == "refresh":
            await user_repo.update_settings(user.id, auto_refresh=not current.auto_refresh)

    if update.callback_query:
        await update.callback_query.answer("Setting updated!", show_alert=False)

    await render_settings_view(update, context)
