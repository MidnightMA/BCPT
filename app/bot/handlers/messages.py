"""Handlers for chat screen view, message history, text sending, editing, and deleting."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.formatters.media import format_delete_confirmation, format_send_message_prompt
from app.bot.formatters.message import format_chat_view
from app.bot.keyboards.common import build_cb, get_cancel_keyboard, get_confirm_keyboard
from app.bot.keyboards.messages import get_chat_screen_keyboard
from app.bot.states.conversation import get_state_manager
from app.core.constants import BotState, CallbackAction
from app.core.logging import get_logger
from app.core.security import authorized_only
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.telegram.adapter import get_telegram_adapter

logger = get_logger(__name__)


async def render_chat_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    offset_id: int = 0,
) -> None:
    """Render the chat message history and action control panel."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    chat_service = ChatService(adapter)
    msg_service = MessageService(adapter)

    chat_dto, perms_dto = await chat_service.get_chat_details(user.id, chat_id)
    messages = await msg_service.get_messages(chat_id=chat_id, limit=10, offset_id=offset_id)

    text = format_chat_view(chat_dto, messages, offset_id=offset_id)
    keyboard = get_chat_screen_keyboard(chat_dto, perms_dto, messages, offset_id=offset_id)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as exc:
            if "Message is not modified" not in str(exc):
                logger.debug(f"Failed to edit chat screen: {exc}")
    elif update.effective_message:
        await update.effective_message.reply_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def trigger_send_message_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    reply_to_msg_id: int | None = None,
) -> None:
    """Prompt the user to enter text for a new message or reply."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    chat_dto = await adapter.get_chat(chat_id)

    state_mgr = await get_state_manager()
    await state_mgr.set_state(
        user.id,
        BotState.WAITING_FOR_MESSAGE,
        data={"chat_id": chat_id, "reply_to": reply_to_msg_id},
    )

    prompt = format_send_message_prompt(chat_dto.title)
    if reply_to_msg_id:
        prompt += f"\n _(Replying to message #{reply_to_msg_id})_ "

    keyboard = get_cancel_keyboard(CallbackAction.CHAT, chat_id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def trigger_edit_message_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
) -> None:
    """Prompt user to type replacement text for an existing message."""
    user = update.effective_user
    if not user:
        return

    state_mgr = await get_state_manager()
    await state_mgr.set_state(
        user.id,
        BotState.WAITING_FOR_EDIT,
        data={"chat_id": chat_id, "message_id": message_id},
    )

    prompt = (
        f"✏️ *Edit Message #{message_id}* \n\n"
        " _Send the updated text for this message below.\n"
        "Or press 'Cancel' to return._ "
    )
    keyboard = get_cancel_keyboard(CallbackAction.CHAT, chat_id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def trigger_delete_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
) -> None:
    """Present a safe confirmation dialog before deleting a message."""
    adapter = get_telegram_adapter()
    chat_dto = await adapter.get_chat(chat_id)

    prompt = format_delete_confirmation(chat_dto.title, message_id)
    keyboard = get_confirm_keyboard(
        confirm_action=CallbackAction.CONFIRM_DEL,
        confirm_args=[chat_id, message_id],
        cancel_action=CallbackAction.CHAT,
        cancel_args=[chat_id],
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def handle_confirm_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
) -> None:
    """Execute message deletion after user confirms dialog."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    msg_service = MessageService(adapter)
    await msg_service.delete_message(user.id, chat_id, message_id)

    if update.callback_query:
        await update.callback_query.answer("🗑 Message deleted successfully.", show_alert=False)

    await render_chat_screen(update, context, chat_id)


async def handle_pin_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
) -> None:
    """Pin message in chat."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    msg_service = MessageService(adapter)
    await msg_service.pin_message(user.id, chat_id, message_id)

    if update.callback_query:
        await update.callback_query.answer("📌 Message pinned!", show_alert=False)

    await render_chat_screen(update, context, chat_id)


@authorized_only
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process incoming user text when waiting for input states."""
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg or not msg.text:
        return

    state_mgr = await get_state_manager()
    state, data = await state_mgr.get_state(user.id)
    adapter = get_telegram_adapter()
    text = msg.text.strip()

    # 1. Sending a new message or reply
    if state == BotState.WAITING_FOR_MESSAGE:
        chat_id = data.get("chat_id")
        reply_to = data.get("reply_to")
        if chat_id:
            msg_service = MessageService(adapter)
            await msg_service.send_text_message(
                user_id=user.id,
                chat_id=chat_id,
                text=text,
                reply_to_msg_id=reply_to,
            )
            await state_mgr.clear_state(user.id)
            await msg.reply_text("✅ *Message Sent!* ", parse_mode="Markdown")
            await render_chat_screen(update, context, chat_id)
            return

    # 2. Editing an existing message
    elif state == BotState.WAITING_FOR_EDIT:
        chat_id = data.get("chat_id")
        message_id = data.get("message_id")
        if chat_id and message_id:
            msg_service = MessageService(adapter)
            await msg_service.edit_message(
                user_id=user.id,
                chat_id=chat_id,
                message_id=message_id,
                new_text=text,
            )
            await state_mgr.clear_state(user.id)
            await msg.reply_text("✅ *Message Edited!* ", parse_mode="Markdown")
            await render_chat_screen(update, context, chat_id)
            return

    # 3. Search queries
    elif state in (BotState.SEARCHING_CHATS, BotState.SEARCHING_MESSAGES):
        from app.bot.handlers.search import process_search_query
        await process_search_query(update, context, state, data, text)
        return

    # Fallback when idle
    await msg.reply_text(
        "💡 Use the control buttons to navigate your Telegram account, or type /start to view the dashboard.",
        parse_mode="Markdown",
    )
