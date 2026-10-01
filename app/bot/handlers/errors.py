"""Global error handler for python-telegram-bot application."""

import html
import traceback

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.keyboards.common import build_cb
from app.core.constants import CallbackAction
from app.core.exceptions import (
    AppException,
    AuthError,
    CircuitBreakerOpenError,
    FloodWaitError,
    PermissionDeniedError,
    RequestQueueFullError,
    TelegramClientError,
)
from app.core.logging import get_logger
from app.utils.telegram_utils import escape_markdown

logger = get_logger(__name__)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the exception and send a user-friendly error message without leaking stack traces."""
    exc = context.error
    logger.error(f"Uncaught exception handling update: {exc}", exc_info=exc)

    if not isinstance(update, Update):
        return

    # Determine user-friendly error response based on domain exception
    if isinstance(exc, (FloodWaitError, CircuitBreakerOpenError, RequestQueueFullError)):
        user_text = exc.user_message
    elif isinstance(exc, PermissionDeniedError):
        user_text = exc.user_message
    elif isinstance(exc, AuthError):
        user_text = exc.user_message
    elif isinstance(exc, AppException):
        user_text = f"⚠️ *Error:* {escape_markdown(exc.user_message)}"
    else:
        user_text = (
            "⚠️ *Unexpected Error* \n\n"
            "An internal error occurred while processing your request. "
            "Please try again or return to the main dashboard."
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Home Dashboard", callback_data=build_cb(CallbackAction.HOME))]
    ])

    try:
        if update.callback_query:
            try:
                await update.callback_query.answer("An error occurred.", show_alert=True)
            except Exception:
                pass
            try:
                await update.callback_query.edit_message_text(
                    text=user_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception:
                pass
        elif update.effective_message:
            await update.effective_message.reply_text(
                text=user_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
    except Exception as notify_err:
        logger.warning(f"Could not send error response to user: {notify_err}")
