"""Handlers for listing dialogs, paginating chats, viewing chat info, and favoriting."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.formatters.chat import format_chat_info, format_chat_list_header
from app.bot.keyboards.chats import get_chat_list_keyboard
from app.bot.keyboards.common import build_cb, get_cancel_keyboard
from app.bot.states.conversation import get_state_manager
from app.cache.cache_service import get_cache_service
from app.core.constants import BotState, CallbackAction, DEFAULT_CHATS_PER_PAGE
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
        try:
            status_msg = "⭐ Added to Favorites!" if is_now_fav else "Chat removed from Favorites."
            await update.callback_query.answer(status_msg, show_alert=False)
        except Exception:
            pass

    # Re-render chat view
    from app.bot.handlers.messages import render_chat_screen
    await render_chat_screen(update, context, chat_id)


async def trigger_open_peer_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Prompt user to enter a Telegram username, public channel, or ID."""
    user = update.effective_user
    if not user:
        return

    state_mgr = await get_state_manager()
    await state_mgr.set_state(user.id, BotState.WAITING_FOR_PEER)

    prompt = (
        "🌐 *Open Telegram User or Public Channel* \n\n"
        "Enter a Telegram username, channel handle, or numeric ID:\n"
        "• Private user: `@username` or user ID\n"
        "• Public channel: `@channelname` or `t.me/channelname`\n\n"
        " _Or press 'Cancel' to return to Home._ "
    )
    keyboard = get_cancel_keyboard(CallbackAction.HOME)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def handle_join_channel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    channel_id: int,
) -> None:
    """Join a public channel and refresh the chat screen."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    chat_service = ChatService(adapter)
    await chat_service.join_channel(user.id, channel_id)

    if update.callback_query:
        try:
            await update.callback_query.answer("✅ Successfully joined channel!", show_alert=True)
        except Exception:
            pass

    from app.bot.handlers.messages import render_chat_screen
    await render_chat_screen(update, context, channel_id)
