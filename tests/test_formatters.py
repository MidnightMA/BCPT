"""Tests for Markdown escaping, text formatting, and view renderers in Bale."""

from datetime import datetime, timezone

from app.bot.formatters.chat import format_home_screen
from app.bot.formatters.message import format_full_message_view, format_message_entry
from app.core.constants import ChatType, MessageType
from app.telegram.adapter import ChatDTO, MessageDTO
from app.utils.telegram_utils import escape_markdown, format_bytes, truncate_text


def test_escape_markdown():
    """Verify Markdown delimiters are properly escaped for Bale."""
    unsafe = "Text with *asterisks* and _underscores_ and [links] and `code`"
    escaped = escape_markdown(unsafe)
    assert "\\*" in escaped
    assert "\\_" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert escape_markdown(None) == ""


def test_truncate_text():
    """Verify text truncation behaves as expected."""
    short = "Hello World"
    assert truncate_text(short, max_length=20) == "Hello World"

    long_text = "a" * 100
    truncated = truncate_text(long_text, max_length=10)
    assert len(truncated) == 10
    assert truncated.endswith("...")


def test_format_bytes():
    """Verify human-readable byte calculations."""
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024 * 2) == "2.0 MB"


def test_format_home_screen():
    """Verify home screen view includes account details and status."""
    summary = {
        "is_connected": True,
        "name": "Mahdi Tester",
        "username": "mahdi_user",
        "user_id": 12345678,
    }
    view = format_home_screen(summary)
    assert "Bale Control Panel" in view
    assert "🟢 Connected" in view
    assert "Mahdi Tester" in view
    assert "@mahdi_user" in view
    assert "12345678" in view


def test_format_message_entry_outgoing():
    """Verify message formatting for outgoing and incoming messages."""
    out_msg = MessageDTO(
        id=10,
        chat_id=100,
        sender_id=1,
        sender_name="You",
        is_outgoing=True,
        text="Testing outgoing message",
        date=datetime.now(timezone.utc),
    )
    formatted = format_message_entry(out_msg)
    assert "➡️" in formatted
    assert "*You*" in formatted
    assert "#10" in formatted
    assert "Testing outgoing message" in formatted

    in_msg = MessageDTO(
        id=11,
        chat_id=100,
        sender_id=2,
        sender_name="Bob *dev*",
        is_outgoing=False,
        text="Hello _world_",
        date=datetime.now(timezone.utc),
        media_type=MessageType.PHOTO,
    )
    formatted_in = format_message_entry(in_msg)
    assert "⬅️" in formatted_in
    assert "Bob \\*dev\\*" in formatted_in
    assert "Hello \\_world\\_" in formatted_in
    assert "📷 Photo" in formatted_in


def test_format_full_message_view():
    """Verify detailed message view rendering with media and un-truncated text."""
    chat = ChatDTO(id=101, title="VIP Channel", chat_type=ChatType.CHANNEL)
    msg = MessageDTO(
        id=42,
        chat_id=101,
        sender_id=999,
        sender_name="You",
        is_outgoing=True,
        text="A full paragraph explaining the announcement without truncation.",
        date=datetime.now(timezone.utc),
        media_type=MessageType.DOCUMENT,
        media_filename="report.pdf",
        media_size=1048576,
        media_mime_type="application/pdf",
        grouped_id=12345,
    )
    view = format_full_message_view(chat, msg, media_count=1)
    assert "#42" in view
    assert "VIP Channel" in view
    assert "➡️ *You*" in view
    assert "A full paragraph explaining the announcement" in view
    assert "report.pdf" in view
    assert "1.0 MB" in view
    assert "application/pdf" in view
    assert "#12345" in view
