"""Security utilities, authorization guards, and file path traversal safeguards."""

import functools
import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.core.logging import get_logger

logger = get_logger(__name__)


def is_user_authorized(user_id: int) -> bool:
    """Check if the given Telegram user ID is authorized in the configuration."""
    settings = get_settings()
    authorized_ids = settings.AUTHORIZED_USER_IDS
    if not authorized_ids:
        # If no users are configured, deny all by default
        return False
    return user_id in authorized_ids


def authorized_only(
    func: Callable[..., Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Decorator for python-telegram-bot handlers.
    Verifies that the effective user is present in the authorized users whitelist.
    Rejects unauthorized access with a generic access denied message.
    """
    @functools.wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        user = update.effective_user
        if not user or not is_user_authorized(user.id):
            user_id_str = str(user.id) if user else "UNKNOWN"
            logger.warning(f"Unauthorized access attempt rejected from user_id={user_id_str}")

            # Send generic access denied response
            denied_msg = "⛔ *Access Denied* : You are not authorized to use this control panel."
            if update.callback_query:
                await update.callback_query.answer("Access Denied", show_alert=True)
                try:
                    await update.callback_query.edit_message_text(denied_msg, parse_mode="Markdown")
                except Exception:
                    pass
            elif update.effective_message:
                await update.effective_message.reply_text(denied_msg, parse_mode="Markdown")
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


def is_safe_path(base_dir: str | Path, target_path: str | Path) -> bool:
    """Verify that target_path resolves strictly within base_dir (prevents traversal attacks)."""
    base = Path(base_dir).resolve()
    target = Path(target_path).resolve()
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def generate_safe_temp_path(original_filename: str | None, temp_dir: str | Path) -> Path:
    """
    Generate a collision-free, safe file path in temp_dir.
    Strips directory components and dangerous characters from the extension.
    """
    base_dir = Path(temp_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    safe_ext = ".tmp"
    if original_filename:
        # Extract extension and sanitize
        raw_ext = Path(original_filename).suffix.lower()
        clean_ext = re.sub(r"[^a-zA-Z0-9_.]", "", raw_ext)
        if clean_ext and len(clean_ext) <= 10:
            safe_ext = clean_ext

    unique_name = f"{uuid.uuid4().hex}{safe_ext}"
    final_path = base_dir / unique_name

    if not is_safe_path(base_dir, final_path):
        raise ValueError(f"Security error: resolved path outside base directory: {final_path}")

    return final_path
