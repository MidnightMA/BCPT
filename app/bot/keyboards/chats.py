"""Inline keyboards for chat and dialog listing with pagination."""

from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.formatters.chat import get_chat_icon
from app.bot.keyboards.common import build_cb
from app.core.constants import CallbackAction
from app.telegram.adapter import ChatDTO
from app.utils.pagination import PaginatedResult
from app.utils.telegram_utils import truncate_text


def get_chat_list_keyboard(
    paginated: PaginatedResult[ChatDTO],
    is_favorites_view: bool = False,
) -> InlineKeyboardMarkup:
    """Build interactive inline keyboard for the dialog list."""
    buttons: List[List[InlineKeyboardButton]] = []
    action_type = CallbackAction.FAVORITES if is_favorites_view else CallbackAction.CHATS

    # 1. Chat item buttons (one per row for clear, touch-friendly tap targets)
    for idx, chat in enumerate(paginated.items, start=1):
        icon = get_chat_icon(chat.chat_type)
        unread = f" 🔴 {chat.unread_count}" if chat.unread_count > 0 else ""
        fav = "⭐ " if chat.is_favorite else ""
        short_title = truncate_text(chat.title, max_length=24)
        label = f"{idx}. {icon} {fav}{short_title}{unread}"
        buttons.append([
            InlineKeyboardButton(
                label,
                callback_data=build_cb(CallbackAction.CHAT, chat.id),
            )
        ])

    # 2. Pagination controls row
    nav_row: List[InlineKeyboardButton] = []
    if paginated.has_prev:
        nav_row.append(
            InlineKeyboardButton("◀️ Prev", callback_data=build_cb(action_type, paginated.prev_page))
        )
    else:
        nav_row.append(InlineKeyboardButton("·", callback_data=build_cb(CallbackAction.NOOP)))

    # Page indicator
    nav_row.append(
        InlineKeyboardButton(
            f"{paginated.page} / {paginated.total_pages}",
            callback_data=build_cb(CallbackAction.NOOP),
        )
    )

    if paginated.has_next:
        nav_row.append(
            InlineKeyboardButton("Next ▶️", callback_data=build_cb(action_type, paginated.next_page))
        )
    else:
        nav_row.append(InlineKeyboardButton("·", callback_data=build_cb(CallbackAction.NOOP)))

    buttons.append(nav_row)

    # 3. Action row: Search & Refresh
    buttons.append([
        InlineKeyboardButton("🔎 Search Dialogs", callback_data=build_cb(CallbackAction.SEARCH_CHATS)),
        InlineKeyboardButton("🔄 Refresh", callback_data=build_cb(action_type, paginated.page)),
    ])

    # 4. Return row: Home
    buttons.append([
        InlineKeyboardButton("🏠 Home Dashboard", callback_data=build_cb(CallbackAction.HOME))
    ])

    return InlineKeyboardMarkup(buttons)
