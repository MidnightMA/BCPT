"""Tests for StateManager and user-isolated conversation states."""

import pytest

from app.bot.states.conversation import StateManager
from app.core.constants import BotState


@pytest.mark.asyncio
async def test_state_transitions(memory_cache):
    """Verify state transitions and payload retrieval."""
    mgr = StateManager(memory_cache)
    user_id = 12345

    # Initial state should be IDLE
    state, data = await mgr.get_state(user_id)
    assert state == BotState.IDLE
    assert data == {}

    # Transition to WAITING_FOR_MESSAGE
    await mgr.set_state(user_id, BotState.WAITING_FOR_MESSAGE, {"chat_id": 999})
    state, data = await mgr.get_state(user_id)
    assert state == BotState.WAITING_FOR_MESSAGE
    assert data == {"chat_id": 999}

    # Clear state back to IDLE
    await mgr.clear_state(user_id)
    state, data = await mgr.get_state(user_id)
    assert state == BotState.IDLE
    assert data == {}


@pytest.mark.asyncio
async def test_user_state_isolation(memory_cache):
    """Verify state is completely isolated between different users."""
    mgr = StateManager(memory_cache)
    user1 = 101
    user2 = 202

    await mgr.set_state(user1, BotState.WAITING_FOR_FILE, {"chat_id": 111})
    await mgr.set_state(user2, BotState.SEARCHING_CHATS, {})

    state1, data1 = await mgr.get_state(user1)
    state2, data2 = await mgr.get_state(user2)

    assert state1 == BotState.WAITING_FOR_FILE
    assert data1 == {"chat_id": 111}

    assert state2 == BotState.SEARCHING_CHATS
    assert data2 == {}

    # Clearing user1 leaves user2 unaffected
    await mgr.clear_state(user1)
    s1, _ = await mgr.get_state(user1)
    s2, _ = await mgr.get_state(user2)

    assert s1 == BotState.IDLE
    assert s2 == BotState.SEARCHING_CHATS
