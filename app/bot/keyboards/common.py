"""Callback data encoding/decoding and common reusable navigation keyboards."""

from typing import Any, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.constants import CallbackAction, MAX_CALLBACK_LEN


def build_cb(action: CallbackAction | str, *args: Any) -> str:
    """
    Construct a compact, colon-separated callback data string:
    Format: 'p:<action>:<arg1>:<arg2>'
    Guarantees the result does not exceed Telegram's 64-byte limit.
    """
    act_str = action.value if isinstance(action, CallbackAction) else str(action)
    parts = ["p", act_str] + [str(a) for a in args]
    data = ":".join(parts)
    encoded_len = len(data.encode("utf-8"))
    if encoded_len > MAX_CALLBACK_LEN:
        raise ValueError(
            f"Callback data exceeds {MAX_CALLBACK_LEN} bytes ({encoded_len} bytes): '{data}'"
        )
    return data


def parse_cb(data: str) -> Tuple[str, List[str]]:
    """
    Parse a callback string into (action, [args]).
    Returns ('unknown', []) if format does not start with 'p:'.
    """
    if not data or not data.startswith("p:"):
        return "unknown", []
    tokens = data.split(":")
    if len(tokens) < 2:
        return "unknown", []
    action = tokens[1]
    args = tokens[2:]
    return action, args


def get_home_keyboard() -> InlineKeyboardMarkup:
    """Build navigation keyboard for the main home dashboard screen."""
    keyboard = [
        [
            InlineKeyboardButton("💬 Chats", callback_data=build_cb(CallbackAction.CHATS, 1)),
            InlineKeyboardButton("⭐ Favorites", callback_data=build_cb(CallbackAction.FAVORITES, 1)),
        ],
        [
            InlineKeyboardButton("🔎 Search Dialogs", callback_data=build_cb(CallbackAction.SEARCH_CHATS)),
            InlineKeyboardButton("⚙️ Settings", callback_data=build_cb(CallbackAction.SETTINGS)),
        ],
        [
            InlineKeyboardButton("🔄 Refresh Dashboard", callback_data=build_cb(CallbackAction.HOME)),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard(return_action: CallbackAction | str = CallbackAction.HOME, *args: Any) -> InlineKeyboardMarkup:
    """Build a simple keyboard with a Cancel button returning to a specific view."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=build_cb(return_action, *args))]
    ])


def get_confirm_keyboard(
    confirm_action: CallbackAction | str,
    confirm_args: List[Any],
    cancel_action: CallbackAction | str,
    cancel_args: List[Any],
) -> InlineKeyboardMarkup:
    """Build a confirmation dialog with [ ✅ Confirm ] and [ ❌ Cancel ] buttons."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=build_cb(confirm_action, *confirm_args)),
            InlineKeyboardButton("❌ Cancel", callback_data=build_cb(cancel_action, *cancel_args)),
        ]
    ])
