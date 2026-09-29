"""Markdown formatters for message history and individual message details in Bale."""

from typing import List, Optional

from app.core.constants import MessageType, TELEGRAM_SAFE_MSG_LEN
from app.telegram.adapter import ChatDTO, MessageDTO
from app.utils.telegram_utils import escape_markdown, format_bytes, format_timestamp, truncate_text

MEDIA_ICONS = {
    MessageType.PHOTO: "📷 Photo",
    MessageType.DOCUMENT: "📁 File",
    MessageType.VIDEO: "🎬 Video",
    MessageType.AUDIO: "🎵 Audio",
    MessageType.VOICE: "🎙 Voice",
    MessageType.STICKER: "🎨 Sticker",
    MessageType.SERVICE: "⚙️ Service Notification",
    MessageType.UNSUPPORTED: "📦 Media",
}


def format_message_entry(msg: MessageDTO) -> str:
    """Format a single message entry with outgoing/incoming markers, time, and sender."""
    is_out = msg.is_outgoing
    direction_icon = "➡️" if is_out else "⬅️"
    sender_name = escape_markdown(msg.sender_name)
    time_str = format_timestamp(msg.date)

    header = f"{direction_icon} *{sender_name}* _({time_str})_ [#{msg.id}]:"

    body_parts = []

    # Media indicator
    if msg.media_type != MessageType.TEXT:
        media_label = MEDIA_ICONS.get(msg.media_type, "📦 Media")
        meta_info = []
        if msg.media_filename:
            meta_info.append(escape_markdown(msg.media_filename))
        if msg.media_size:
            meta_info.append(format_bytes(msg.media_size))
        meta_str = f" ({', '.join(meta_info)})" if meta_info else ""
        body_parts.append(f" _[{media_label}{meta_str}]_ ")

    # Reply reference
    if msg.reply_to_msg_id:
        body_parts.append(f"↪️ _In reply to #{msg.reply_to_msg_id}_ ")

    # Message text content
    if msg.text:
        clean_text = escape_markdown(truncate_text(msg.text, max_length=300))
        body_parts.append(clean_text)

    content = " ".join(body_parts) if body_parts else " _[Empty message]_ "
    return f"{header}\n{content}"


def format_chat_view(
    chat: ChatDTO,
    messages: List[MessageDTO],
    offset_id: int = 0,
) -> str:
    """Render the active chat screen with message history and navigation details."""
    chat_title = escape_markdown(chat.title)
    lines = [
        f"💬 *{chat_title}* ",
        f" *Chat ID:* {chat.id}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if not messages:
        lines.append(" _No messages in this chat yet._ ")
    else:
        rendered_entries = [format_message_entry(m) for m in messages]
        lines.append("\n\n".join(rendered_entries))

    lines.extend([
        "\n━━━━━━━━━━━━━━━━━━━━",
        " _Select an action below:_ ",
    ])

    full_text = "\n".join(lines)
    # Guarantee we do not exceed safe message length limits
    if len(full_text) > TELEGRAM_SAFE_MSG_LEN:
        return full_text[:TELEGRAM_SAFE_MSG_LEN] + "\n\n _[Message history truncated due to length]_ "
    return full_text


def format_full_message_view(
    chat: ChatDTO,
    msg: MessageDTO,
    media_count: int = 0,
    media_notes: Optional[List[str]] = None,
) -> str:
    """Format full, comprehensive message view for a single targeted message."""
    chat_title = escape_markdown(chat.title)
    is_out = msg.is_outgoing
    direction_icon = "➡️" if is_out else "⬅️"
    sender_name = escape_markdown(msg.sender_name)
    time_str = format_timestamp(msg.date)

    lines = [
        f"💬 *Message #{msg.id}* in *{chat_title}* ",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{direction_icon} *{sender_name}* _({time_str})_",
    ]

    if msg.reply_to_msg_id:
        lines.append(f"↪️ _In reply to message #{msg.reply_to_msg_id}_")

    # Media metadata section
    if msg.media_type != MessageType.TEXT or media_count > 0:
        media_label = MEDIA_ICONS.get(msg.media_type, "📦 Media")
        meta_items = []
        if msg.media_filename:
            meta_items.append(f"Filename: {escape_markdown(msg.media_filename)}")
        if msg.media_size:
            meta_items.append(f"Size: {format_bytes(msg.media_size)}")
        if msg.media_mime_type:
            meta_items.append(f"Type: {escape_markdown(msg.media_mime_type)}")
        if msg.grouped_id:
            meta_items.append(f"Album: #{msg.grouped_id}")
        if media_count > 1:
            meta_items.append(f"Total media items: {media_count}")

        meta_desc = " • ".join(meta_items) if meta_items else "Attached media retrieved"
        lines.append(f"\n📎 *{media_label}:* {meta_desc}")

    if media_notes:
        for note in media_notes:
            lines.append(f"ℹ️ _{escape_markdown(note)}_")

    # Full message text (without truncation up to safe telegram limits)
    if msg.text:
        clean_text = escape_markdown(msg.text)
        lines.append(f"\n📝 *Content:*\n{clean_text}")
    elif msg.media_type == MessageType.TEXT:
        lines.append("\n _[Empty text message]_ ")

    lines.extend([
        "\n━━━━━━━━━━━━━━━━━━━━",
        " _Select an action below:_ ",
    ])

    full_text = "\n".join(lines)
    if len(full_text) > TELEGRAM_SAFE_MSG_LEN:
        return full_text[:TELEGRAM_SAFE_MSG_LEN] + "\n\n _[Text truncated due to Telegram size limit]_ "
    return full_text
