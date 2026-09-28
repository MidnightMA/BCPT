"""Inline keyboards for chat message screen, pagination, and message actions."""

from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.common import build_cb
from app.core.constants import CallbackAction
from app.telegram.adapter import ChatDTO, ChatPermissionsDTO, MessageDTO


def get_chat_screen_keyboard(
    chat: ChatDTO,
    perms: ChatPermissionsDTO,
    messages: List[MessageDTO],
    offset_id: int = 0,
) -> InlineKeyboardMarkup:
    """Build the main action and navigation keyboard for the active chat view."""
    buttons: List[List[InlineKeyboardButton]] = []

    # 1. Primary write actions (conditionally displayed based on evaluated permissions)
    write_row: List[InlineKeyboardButton] = []
    if perms.can_send_messages or perms.can_post_messages:
        write_row.append(
            InlineKeyboardButton("✍️ Send Message", callback_data=build_cb(CallbackAction.ACT_SEND, chat.id))
        )
    if perms.can_send_media or perms.can_post_messages:
        write_row.append(
            InlineKeyboardButton("📎 Send File", callback_data=build_cb(CallbackAction.ACT_FILE, chat.id))
        )
    if write_row:
        buttons.append(write_row)

    # 2. History pagination row (Older / Newer / Refresh)
    # If we have messages, oldest message in view provides the offset_id for older messages
    nav_row: List[InlineKeyboardButton] = []
    if messages:
        oldest_id = messages[0].id  # List is sorted chronological, so first element is oldest
        nav_row.append(
            InlineKeyboardButton("◀️ Older", callback_data=build_cb(CallbackAction.MSGS, chat.id, oldest_id))
        )
    else:
        nav_row.append(InlineKeyboardButton("·", callback_data=build_cb(CallbackAction.NOOP)))

    nav_row.append(
        InlineKeyboardButton("🔄 Refresh", callback_data=build_cb(CallbackAction.CHAT, chat.id))
    )

    if offset_id > 0:
        # We are browsing older history, show Newer button to jump back to latest
        nav_row.append(
            InlineKeyboardButton("Newest ▶️", callback_data=build_cb(CallbackAction.CHAT, chat.id))
        )
    else:
        nav_row.append(InlineKeyboardButton("·", callback_data=build_cb(CallbackAction.NOOP)))

    buttons.append(nav_row)

    # 3. Message Quick Action Picker (if messages exist, let user select one to reply/edit/delete)
    if messages:
        picker_row: List[InlineKeyboardButton] = []
        # Offer quick selection for the last 3-4 messages
        recent_msgs = messages[-3:]
        for m in recent_msgs:
            sender_tag = "You" if m.is_outgoing else (m.sender_name[:6] if m.sender_name else "User")
            picker_row.append(
                InlineKeyboardButton(
                    f"#{m.id} ({sender_tag})",
                    callback_data=build_cb(CallbackAction.ACT_REPLY, chat.id, m.id),
                )
            )
        buttons.append(picker_row)

    # 4. Search and Info row
    fav_label = "❌ Unstar" if chat.is_favorite else "⭐ Star"
    buttons.append([
        InlineKeyboardButton("🔎 Search", callback_data=build_cb(CallbackAction.SEARCH_MSGS, chat.id)),
        InlineKeyboardButton("ℹ️ Info", callback_data=build_cb(CallbackAction.ACT_INFO, chat.id)),
        InlineKeyboardButton(fav_label, callback_data=build_cb(CallbackAction.ACT_FAV, chat.id)),
    ])

    # 5. Back navigation row
    buttons.append([
        InlineKeyboardButton("◀️ Back to Chats", callback_data=build_cb(CallbackAction.CHATS, 1)),
        InlineKeyboardButton("🏠 Home", callback_data=build_cb(CallbackAction.HOME)),
    ])

    return InlineKeyboardMarkup(buttons)


def get_message_detail_keyboard(
    chat_id: int,
    message: MessageDTO,
    perms: ChatPermissionsDTO,
) -> InlineKeyboardMarkup:
    """Build action keyboard for a single targeted message (reply, edit, delete, pin)."""
    buttons: List[List[InlineKeyboardButton]] = []

    # Reply & Edit row
    action_row: List[InlineKeyboardButton] = [
        InlineKeyboardButton("↩️ Reply", callback_data=build_cb(CallbackAction.ACT_REPLY, chat_id, message.id))
    ]
    if message.can_edit and perms.can_edit_messages:
        action_row.append(
            InlineKeyboardButton("✏️ Edit", callback_data=build_cb(CallbackAction.ACT_EDIT, chat_id, message.id))
        )
    buttons.append(action_row)

    # Pin & Delete row
    manage_row: List[InlineKeyboardButton] = []
    if perms.can_pin_messages:
        manage_row.append(
            InlineKeyboardButton("📌 Pin", callback_data=build_cb(CallbackAction.ACT_PIN, chat_id, message.id))
        )
    if perms.can_delete_messages or message.can_delete:
        manage_row.append(
            InlineKeyboardButton("🗑 Delete", callback_data=build_cb(CallbackAction.ACT_DEL, chat_id, message.id))
        )
    if manage_row:
        buttons.append(manage_row)

    # Return row
    buttons.append([
        InlineKeyboardButton("◀️ Back to Chat", callback_data=build_cb(CallbackAction.CHAT, chat_id))
    ])

    return InlineKeyboardMarkup(buttons)
