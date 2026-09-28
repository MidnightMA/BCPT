"""Handlers for listing dialogs, paginating chats, viewing chat info, and favoriting."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.formatters.chat import format_chat_info, format_chat_list_header
from app.bot.keyboards.chats import get_chat_list_keyboard
from app.bot.keyboards.common import build_cb
from app.cache.cache_service import get_cache_service
from app.core.constants import CallbackAction, DEFAULT_CHATS_PER_PAGE
from app.core.logging import get_logger
from app.core.security import authorized_only
from app.services.chat_service import ChatService
from app.telegram.adapter import get_telegram_adapter

logger = get_logger(__name__)


async def render_chats_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 1,
    favorites_only: bool = False,
) -> None:
    """Render paginated list of chats or favorites."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    cache_svc = await get_cache_service()
    chat_service = ChatService(adapter, cache_svc)

    paginated = await chat_service.get_dialogs_paginated(
        user_id=user.id,
        page=page,
        per_page=DEFAULT_CHATS_PER_PAGE,
        favorites_only=favorites_only,
    )

    text = format_chat_list_header(paginated, is_favorites_view=favorites_only)
    keyboard = get_chat_list_keyboard(paginated, is_favorites_view=favorites_only)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as exc:
            if "Message is not modified" not in str(exc):
                logger.debug(f"Failed to edit chat list: {exc}")
    elif update.effective_message:
        await update.effective_message.reply_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def render_chat_info_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """Display comprehensive metadata and permissions for a chat."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    chat_service = ChatService(adapter)
    chat_dto, perms_dto = await chat_service.get_chat_details(user.id, chat_id)

    text = format_chat_info(chat_dto, perms_dto)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Chat", callback_data=build_cb(CallbackAction.CHAT, chat_id)),
            InlineKeyboardButton("🏠 Home", callback_data=build_cb(CallbackAction.HOME)),
        ]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def handle_toggle_favorite(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """Toggle favorite status of a chat and refresh view."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    chat_service = ChatService(adapter)
    is_now_fav = await chat_service.toggle_favorite(user.id, chat_id)

    if update.callback_query:
        status_msg = "⭐ Added to Favorites!" if is_now_fav else "Chat removed from Favorites."
        await update.callback_query.answer(status_msg, show_alert=False)

    # Re-render chat view
    from app.bot.handlers.messages import render_chat_screen
    await render_chat_screen(update, context, chat_id)
