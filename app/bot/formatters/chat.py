"""Markdown formatters for home screen, chat lists, and chat info views in Bale."""

from typing import Any, Dict, List, Optional

from app.core.constants import ChatType
from app.telegram.adapter import ChatDTO, ChatPermissionsDTO
from app.utils.pagination import PaginatedResult
from app.utils.telegram_utils import escape_markdown, truncate_text

CHAT_TYPE_ICONS = {
    ChatType.USER: "👤",
    ChatType.GROUP: "👥",
    ChatType.SUPERGROUP: "👥",
    ChatType.CHANNEL: "📢",
    ChatType.BOT: "🤖",
    ChatType.SAVED_MESSAGES: "💾",
}


def get_chat_icon(chat_type: ChatType) -> str:
    """Return an icon representing the chat type."""
    return CHAT_TYPE_ICONS.get(chat_type, "💬")


def format_home_screen(account_summary: Dict[str, Any]) -> str:
    """Render the main home dashboard view."""
    is_connected = account_summary.get("is_connected", False)
    status_icon = "🟢 Connected" if is_connected else "🔴 Disconnected"
    name = escape_markdown(account_summary.get("name", "Unknown Account"))
    username = account_summary.get("username")
    user_id = account_summary.get("user_id")

    lines = [
        "🎛 *Bale Control Panel (Telegram)* ",
        "━━━━━━━━━━━━━━━━━━━━",
        f" *Status:* {status_icon}",
        f" *Account:* {name}",
    ]

    if username:
        lines.append(f" *Username:* @{escape_markdown(username)}")
    if user_id:
        lines.append(f" *User ID:* {user_id}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        " _Select an option below to control your Telegram account:_ ",
    ])

    return "\n".join(lines)


def format_chat_list_header(
    paginated: PaginatedResult[ChatDTO],
    is_favorites_view: bool = False,
    query: Optional[str] = None,
) -> str:
    """Render the header and items summary for dialogs list."""
    if query:
        title = f"🔎 *Search Results:* _{escape_markdown(query)}_"
    elif is_favorites_view:
        title = "⭐ *Favorite Chats* "
    else:
        title = "💬 *All Dialogs* "

    lines = [
        title,
        f" _Page {paginated.page} of {paginated.total_pages} ({paginated.total_items} total)_ ",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if not paginated.items:
        lines.append("\n _No dialogs found._ ")
    else:
        for idx, chat in enumerate(paginated.items, start=1):
            icon = get_chat_icon(chat.chat_type)
            fav_mark = "⭐ " if chat.is_favorite else ""
            unread_mark = f" 🔴 *{chat.unread_count}* " if chat.unread_count > 0 else ""
            clean_title = escape_markdown(truncate_text(chat.title, max_length=28))
            lines.append(f"{idx}. {icon} {fav_mark} *{clean_title}* {unread_mark}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(" _Click a button below to open a chat:_ ")
    return "\n".join(lines)


def format_chat_info(chat: ChatDTO, perms: ChatPermissionsDTO) -> str:
    """Render detailed chat information and permissions snapshot."""
    icon = get_chat_icon(chat.chat_type)
    title = escape_markdown(chat.title)
    chat_type_name = chat.chat_type.value.capitalize()

    lines = [
        f"{icon} *Chat Information* ",
        "━━━━━━━━━━━━━━━━━━━━",
        f" *Title:* {title}",
        f" *Chat ID:* {chat.id}",
        f" *Type:* {chat_type_name}",
    ]

    if chat.username:
        lines.append(f" *Username:* @{escape_markdown(chat.username)}")
    if chat.participants_count:
        lines.append(f" *Members:* {chat.participants_count:,}")
    if chat.unread_count > 0:
        lines.append(f" *Unread Messages:* {chat.unread_count}")
    lines.append(f" *Bookmarked:* {'Yes ⭐' if chat.is_favorite else 'No'}")

    # Permissions breakdown
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "🛡 *Your Account Capabilities:* ",
        f"• Send Messages: {'✅' if perms.can_send_messages else '❌'}",
        f"• Send Media: {'✅' if perms.can_send_media else '❌'}",
        f"• Post to Channel: {'✅' if perms.can_post_messages else '❌'}",
        f"• Edit Messages: {'✅' if perms.can_edit_messages else '❌'}",
        f"• Delete Messages: {'✅' if perms.can_delete_messages else '❌'}",
        f"• Pin Messages: {'✅' if perms.can_pin_messages else '❌'}",
        f"• Admin Status: {'👑 Creator' if perms.is_creator else ('🛡 Admin' if perms.is_admin else '👤 Member')}",
    ])

    return "\n".join(lines)
