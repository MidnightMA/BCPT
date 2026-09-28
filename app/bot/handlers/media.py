"""Handlers for file/media upload prompt and incoming media reception."""

from pathlib import Path
from typing import Optional

from telegram import Document, PhotoSize, Update, Video, Audio, Voice
from telegram.ext import ContextTypes

from app.bot.formatters.media import format_send_file_prompt
from app.bot.keyboards.common import get_cancel_keyboard
from app.bot.states.conversation import get_state_manager
from app.core.config import get_settings
from app.core.constants import BotState, CallbackAction
from app.core.logging import get_logger
from app.core.security import authorized_only, generate_safe_temp_path
from app.services.media_service import MediaService
from app.telegram.adapter import get_telegram_adapter
from app.utils.cleanup import safe_remove_file

logger = get_logger(__name__)


async def trigger_send_file_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """Prompt user to upload a file/media attachment for the chat."""
    user = update.effective_user
    if not user:
        return

    adapter = get_telegram_adapter()
    chat_dto = await adapter.get_chat(chat_id)

    state_mgr = await get_state_manager()
    await state_mgr.set_state(
        user.id,
        BotState.WAITING_FOR_FILE,
        data={"chat_id": chat_id},
    )

    prompt = format_send_file_prompt(chat_dto.title)
    keyboard = get_cancel_keyboard(CallbackAction.CHAT, chat_id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


@authorized_only
async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download received media from bot and upload through Telethon to the target chat."""
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    state_mgr = await get_state_manager()
    state, data = await state_mgr.get_state(user.id)

    if state != BotState.WAITING_FOR_FILE:
        # Not waiting for a file, ignore or inform user
        return

    chat_id = data.get("chat_id")
    if not chat_id:
        await state_mgr.clear_state(user.id)
        return

    settings = get_settings()
    caption = msg.caption or ""

    # Detect Telegram file object
    tg_file_obj = None
    original_filename = None

    if msg.document:
        tg_file_obj = msg.document
        original_filename = msg.document.file_name
    elif msg.photo:
        # Take the highest resolution photo
        tg_file_obj = msg.photo[-1]
        original_filename = "photo.jpg"
    elif msg.video:
        tg_file_obj = msg.video
        original_filename = msg.video.file_name or "video.mp4"
    elif msg.audio:
        tg_file_obj = msg.audio
        original_filename = msg.audio.file_name or "audio.mp3"
    elif msg.voice:
        tg_file_obj = msg.voice
        original_filename = "voice.ogg"

    if not tg_file_obj:
        await msg.reply_text("⚠️ Unsupported file format. Please send a document, photo, video, or audio file.")
        return

    status_msg = await msg.reply_text("⏳ _Downloading file to temporary storage..._ ", parse_mode="Markdown")

    temp_path: Optional[Path] = None
    try:
        temp_path = generate_safe_temp_path(original_filename, settings.TEMP_DIR)
        bot_file = await tg_file_obj.get_file()
        await bot_file.download_to_drive(custom_path=temp_path)

        await status_msg.edit_text("📤 _Uploading via your Telegram account..._ ", parse_mode="Markdown")

        adapter = get_telegram_adapter()
        media_service = MediaService(adapter)
        await media_service.send_file(
            user_id=user.id,
            chat_id=chat_id,
            temp_file_path=temp_path,
            caption=caption if caption else None,
        )

        await state_mgr.clear_state(user.id)
        await status_msg.edit_text("✅ *File Uploaded Successfully!* ", parse_mode="Markdown")

        # Refresh chat view
        from app.bot.handlers.messages import render_chat_screen
        await render_chat_screen(update, context, chat_id)

    except Exception as exc:
        logger.error(f"Error handling media upload: {exc}", exc_info=True)
        if temp_path:
            safe_remove_file(temp_path)
        await status_msg.edit_text(
            f"❌ *Upload Failed:* {exc}",
            parse_mode="Markdown",
        )
