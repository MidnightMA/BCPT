"""Handlers for chat screen view, message history, text sending, editing, and deleting."""

from typing import List

from telegram import InputMediaPhoto, InputMediaVideo, Update
from telegram.ext import ContextTypes

from app.bot.formatters.media import format_delete_confirmation, format_send_message_prompt
from app.bot.formatters.message import format_chat_view, format_full_message_view
from app.bot.keyboards.common import build_cb, get_cancel_keyboard, get_confirm_keyboard
from app.bot.keyboards.messages import get_chat_screen_keyboard, get_message_detail_keyboard
from app.bot.states.conversation import get_state_manager
from app.core.config import get_settings
from app.core.constants import BotState, CallbackAction, ChatType, MessageType
from app.core.logging import get_logger
from app.core.security import authorized_only
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.telegram.adapter import MediaItemDTO, get_telegram_adapter
from app.utils.cleanup import safe_remove_file
from app.utils.telegram_utils import escape_markdown

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


async def _send_individual_media_to_bale(bot, user_id: int, item: MediaItemDTO) -> None:
    """Send a single media item via Bale bot using the appropriate Telegram Bot API method."""
    try:
        caption = escape_markdown(item.caption) if item.caption else None
        with open(item.file_path, "rb") as f:
            if item.media_type == MessageType.PHOTO:
                await bot.send_photo(chat_id=user_id, photo=f, caption=caption, parse_mode="Markdown")
            elif item.media_type == MessageType.VIDEO:
                await bot.send_video(chat_id=user_id, video=f, caption=caption, parse_mode="Markdown")
            elif item.media_type == MessageType.AUDIO:
                await bot.send_audio(chat_id=user_id, audio=f, caption=caption, parse_mode="Markdown")
            elif item.media_type == MessageType.VOICE:
                await bot.send_voice(chat_id=user_id, voice=f, caption=caption, parse_mode="Markdown")
            else:
                filename = item.filename or item.file_path.name
                await bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=filename,
                    caption=caption,
                    parse_mode="Markdown",
                )
    except Exception as exc:
        logger.error(f"Error sending individual media '{item.filename}' to Bale user {user_id}: {exc}")


async def render_message_detail_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
) -> None:
    """Retrieve complete message content, download and send all media via Bale, and display detail panel."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    chat_service = ChatService(adapter)
    msg_service = MessageService(adapter)
    settings = get_settings()

    chat_dto, perms_dto = await chat_service.get_chat_details(user.id, chat_id)
    msg_dto = await msg_service.get_message(chat_id, message_id)

    if update.callback_query:
        await update.callback_query.answer("⏳ Retrieving message and media...", show_alert=False)

    media_items: List[MediaItemDTO] = []
    media_notes: List[str] = []
    try:
        media_items = await msg_service.download_message_media(chat_id, message_id, settings.TEMP_DIR)
        if media_items:
            # Multi-media / album handling
            if len(media_items) > 1:
                all_photos_or_videos = all(
                    item.media_type in (MessageType.PHOTO, MessageType.VIDEO)
                    for item in media_items
                )
                album_sent = False
                if all_photos_or_videos:
                    try:
                        media_group = []
                        open_files = []
                        for idx, item in enumerate(media_items):
                            f = open(item.file_path, "rb")
                            open_files.append(f)
                            caption = escape_markdown(item.caption) if (idx == 0 and item.caption) else None
                            if item.media_type == MessageType.PHOTO:
                                media_group.append(InputMediaPhoto(media=f, caption=caption, parse_mode="Markdown"))
                            else:
                                media_group.append(InputMediaVideo(media=f, caption=caption, parse_mode="Markdown"))
                        try:
                            await context.bot.send_media_group(chat_id=user.id, media=media_group)
                            album_sent = True
                        finally:
                            for f in open_files:
                                f.close()
                    except Exception as exc:
                        logger.warning(f"send_media_group failed or unsupported on Bale endpoint: {exc}")
                        album_sent = False

                if not album_sent:
                    for item in media_items:
                        await _send_individual_media_to_bale(context.bot, user.id, item)

            elif len(media_items) == 1:
                await _send_individual_media_to_bale(context.bot, user.id, media_items[0])

    except Exception as exc:
        logger.error(f"Error downloading or sending media for message #{message_id}: {exc}", exc_info=True)
        media_notes.append(f"Media retrieval note: {exc}")
    finally:
        for item in media_items:
            safe_remove_file(item.file_path)

    text = format_full_message_view(
        chat=chat_dto,
        msg=msg_dto,
        media_count=len(media_items),
        media_notes=media_notes if media_notes else None,
    )
    keyboard = get_message_detail_keyboard(chat_id, msg_dto, perms_dto)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception:
            await context.bot.send_message(
                chat_id=user.id,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def trigger_prompt_view_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """Prompt user to enter a specific message ID / code to view."""
    user = update.effective_user
    if not user:
        return

    state_mgr = await get_state_manager()
    await state_mgr.set_state(
        user.id,
        BotState.WAITING_FOR_MSG_ID,
        data={"chat_id": chat_id},
    )

    prompt = (
        "👁 *View Message Details* \n\n"
        "Enter the Message ID / Code (e.g. `123` or `#123`):\n"
        " _The complete message content and all attached media will be retrieved and displayed._ \n\n"
        " _Or press 'Cancel' to return to Chat._ "
    )
    keyboard = get_cancel_keyboard(CallbackAction.CHAT, chat_id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


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

    # 3. View message by ID / code
    elif state == BotState.WAITING_FOR_MSG_ID:
        chat_id = data.get("chat_id")
        clean_code = text.lstrip("#").strip()
        if not clean_code.isdigit():
            await msg.reply_text(
                "⚠️ *Invalid Message ID:* Please enter a valid number (e.g. `105` or `#105`).",
                parse_mode="Markdown",
            )
            return

        message_id = int(clean_code)
        await state_mgr.clear_state(user.id)
        try:
            await render_message_detail_view(update, context, chat_id=chat_id, message_id=message_id)
        except Exception as exc:
            await msg.reply_text(
                f"⚠️ *Error retrieving message #{message_id}:* {exc}",
                parse_mode="Markdown",
            )
        return

    # 4. Open peer / resolve user or channel
    elif state == BotState.WAITING_FOR_PEER:
        chat_service = ChatService(adapter)
        try:
            chat_dto, perms_dto = await chat_service.resolve_and_get_chat(user.id, text)
            await state_mgr.clear_state(user.id)
            if chat_dto.chat_type == ChatType.USER:
                await msg.reply_text(
                    f"👤 *Resolved User:* *{escape_markdown(chat_dto.title)}* (ID: `{chat_dto.id}`)",
                    parse_mode="Markdown",
                )
            elif chat_dto.chat_type == ChatType.CHANNEL:
                await msg.reply_text(
                    f"📢 *Resolved Channel:* *{escape_markdown(chat_dto.title)}* (ID: `{chat_dto.id}`)",
                    parse_mode="Markdown",
                )
            else:
                await msg.reply_text(
                    f"💬 *Resolved:* *{escape_markdown(chat_dto.title)}*",
                    parse_mode="Markdown",
                )
            await render_chat_screen(update, context, chat_id=chat_dto.id)
        except Exception as exc:
            await msg.reply_text(
                f"⚠️ *Resolution Failed:* Could not find or access *{escape_markdown(text)}*.\n\n"
                f" _Reason: {escape_markdown(str(exc))}_\n"
                "Please verify the username/ID and ensure it is public or valid.",
                parse_mode="Markdown",
            )
        return

    # 5. Search queries
    elif state in (BotState.SEARCHING_CHATS, BotState.SEARCHING_MESSAGES):
        from app.bot.handlers.search import process_search_query
        await process_search_query(update, context, state, data, text)
        return

    # Fallback when idle
    await msg.reply_text(
        "💡 Use the control buttons to navigate your Telegram account, or type /start to view the dashboard.",
        parse_mode="Markdown",
    )
