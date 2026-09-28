"""Inline keyboards for user settings and notification preferences."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.common import build_cb
from app.core.constants import CallbackAction
from app.database.models import UserSetting


def get_settings_keyboard(settings: UserSetting) -> InlineKeyboardMarkup:
    """Build settings toggles keyboard."""
    notif_icon = "🔔 Enabled" if settings.notifications_enabled else "🔕 Muted"
    fav_notif_icon = "⭐ Favorites Only" if settings.notify_favorites_only else "🌐 All Chats"
    refresh_icon = "⚡ On" if settings.auto_refresh else "⏸ Off"

    keyboard = [
        [
            InlineKeyboardButton("Notifications:", callback_data=build_cb(CallbackAction.NOOP)),
            InlineKeyboardButton(notif_icon, callback_data=build_cb(CallbackAction.TOGGLE_SETTING, "notif")),
        ],
        [
            InlineKeyboardButton("Notification Filter:", callback_data=build_cb(CallbackAction.NOOP)),
            InlineKeyboardButton(fav_notif_icon, callback_data=build_cb(CallbackAction.TOGGLE_SETTING, "fav_only")),
        ],
        [
            InlineKeyboardButton("Auto-Refresh:", callback_data=build_cb(CallbackAction.NOOP)),
            InlineKeyboardButton(refresh_icon, callback_data=build_cb(CallbackAction.TOGGLE_SETTING, "refresh")),
        ],
        [
            InlineKeyboardButton("🏠 Home Dashboard", callback_data=build_cb(CallbackAction.HOME))
        ],
    ]

    return InlineKeyboardMarkup(keyboard)
