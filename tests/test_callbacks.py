"""Tests for callback data construction, parsing, and length constraints."""

import pytest

from app.bot.keyboards.common import build_cb, parse_cb
from app.core.constants import CallbackAction, MAX_CALLBACK_LEN


def test_build_and_parse_callback():
    """Verify that build_cb and parse_cb round-trip cleanly."""
    cb_data = build_cb(CallbackAction.CHAT, 123456789)
    assert cb_data == "p:chat:123456789"

    action, args = parse_cb(cb_data)
    assert action == "chat"
    assert args == ["123456789"]


def test_multi_argument_callback():
    """Verify multi-argument callbacks parse correctly."""
    cb_data = build_cb(CallbackAction.MSGS, -1001234567890, 42)
    assert cb_data == "p:msgs:-1001234567890:42"

    action, args = parse_cb(cb_data)
    assert action == "msgs"
    assert args == ["-1001234567890", "42"]


def test_callback_length_limit():
    """Verify build_cb raises ValueError when constructed string exceeds 64 bytes."""
    short_data = build_cb(CallbackAction.ACT_SEND, 123456)
    assert len(short_data.encode("utf-8")) <= MAX_CALLBACK_LEN

    # Oversized payload
    long_arg = "x" * 60
    with pytest.raises(ValueError, match="Callback data exceeds 64 bytes"):
        build_cb(CallbackAction.ACT_SEND, long_arg)


def test_invalid_callback_parsing():
    """Verify malformed callback strings parse safely without crashing."""
    assert parse_cb("") == ("unknown", [])
    assert parse_cb("random_string_without_prefix") == ("unknown", [])
    assert parse_cb("p:") == ("unknown", [])
