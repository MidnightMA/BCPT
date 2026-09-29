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


def test_new_features_callbacks():
    """Verify callback building and parsing for peer opening, joining, and viewing full messages."""
    # Open peer
    open_peer_cb = build_cb(CallbackAction.OPEN_PEER)
    assert open_peer_cb == "p:opeer"
    act, args = parse_cb(open_peer_cb)
    assert act == "opeer"
    assert args == []

    # Join channel
    join_cb = build_cb(CallbackAction.JOIN_CHAN, -1001234567890)
    assert join_cb == "p:jchan:-1001234567890"
    act, args = parse_cb(join_cb)
    assert act == "jchan"
    assert args == ["-1001234567890"]

    # View message
    view_msg_cb = build_cb(CallbackAction.VIEW_MSG, 101, 42)
    assert view_msg_cb == "p:vmsg:101:42"
    act, args = parse_cb(view_msg_cb)
    assert act == "vmsg"
    assert args == ["101", "42"]

    # Prompt view message
    prompt_cb = build_cb(CallbackAction.PROMPT_VIEW_MSG, 101)
    assert prompt_cb == "p:pvmsg:101"
    act, args = parse_cb(prompt_cb)
    assert act == "pvmsg"
    assert args == ["101"]


def test_custom_answer_actions():
    """Verify actions requiring individual toast alerts are categorized."""
    from app.bot.handlers.callbacks import ACTIONS_WITH_CUSTOM_ANSWER
    assert CallbackAction.VIEW_MSG not in ACTIONS_WITH_CUSTOM_ANSWER
    assert CallbackAction.CONFIRM_DEL in ACTIONS_WITH_CUSTOM_ANSWER
    assert CallbackAction.ACT_PIN in ACTIONS_WITH_CUSTOM_ANSWER
    assert CallbackAction.ACT_FAV in ACTIONS_WITH_CUSTOM_ANSWER
    assert CallbackAction.JOIN_CHAN in ACTIONS_WITH_CUSTOM_ANSWER
    assert CallbackAction.TOGGLE_SETTING in ACTIONS_WITH_CUSTOM_ANSWER
