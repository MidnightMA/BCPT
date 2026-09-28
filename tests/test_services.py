"""Tests for business services (Chat, Message, Media, and Search)."""

from pathlib import Path

import pytest

from app.services.chat_service import ChatService
from app.services.media_service import MediaService
from app.services.message_service import MessageService
from app.services.search_service import SearchService


@pytest.mark.asyncio
async def test_chat_service_dialogs(mock_adapter, mock_settings):
    """Verify dialog fetching and pagination through ChatService."""
    svc = ChatService(mock_adapter)
    paginated = await svc.get_dialogs_paginated(user_id=111222333, page=1, per_page=2)

    assert len(paginated.items) == 2
    assert paginated.total_items == 3
    assert paginated.total_pages == 2
    assert paginated.page == 1


@pytest.mark.asyncio
async def test_chat_service_favorites_toggle(mock_adapter, mock_settings):
    """Verify marking and unmarking a chat as favorite."""
    svc = ChatService(mock_adapter)
    user_id = 111222333
    chat_id = 101

    # First toggle: should become favorite
    is_fav1 = await svc.toggle_favorite(user_id, chat_id)
    assert is_fav1 is True

    # Second toggle: should be removed
    is_fav2 = await svc.toggle_favorite(user_id, chat_id)
    assert is_fav2 is False


@pytest.mark.asyncio
async def test_message_service_operations(mock_adapter, mock_settings):
    """Verify message sending, editing, and deleting via MessageService."""
    svc = MessageService(mock_adapter)
    user_id = 111222333
    chat_id = 101

    # 1. Send message
    sent = await svc.send_text_message(user_id, chat_id, "Hello test message")
    assert sent.text == "Hello test message"
    assert sent.chat_id == chat_id

    # 2. Edit message
    edited = await svc.edit_message(user_id, chat_id, sent.id, "Updated text")
    assert edited.text == "Updated text"

    # 3. Delete message
    deleted = await svc.delete_message(user_id, chat_id, sent.id)
    assert deleted is True


@pytest.mark.asyncio
async def test_media_service_cleanup(mock_adapter, mock_settings, tmp_path):
    """Verify that MediaService uploads file and guarantees deletion of local temp file."""
    svc = MediaService(mock_adapter)
    user_id = 111222333
    chat_id = 101

    # Create dummy temp file
    temp_file = tmp_path / "test_upload.pdf"
    temp_file.write_text("dummy binary content")
    assert temp_file.exists() is True

    # Send file
    dto = await svc.send_file(
        user_id=user_id,
        chat_id=chat_id,
        temp_file_path=temp_file,
        caption="My Document",
    )
    assert dto.media_filename == "file.pdf"

    # Verify temp file was deleted in finally block
    assert temp_file.exists() is False


@pytest.mark.asyncio
async def test_search_service(mock_adapter, mock_settings):
    """Verify chat and message querying through SearchService."""
    svc = SearchService(mock_adapter)

    # Search dialogs
    res_chats = await svc.search_chats(query="Alice")
    assert len(res_chats.items) == 1
    assert res_chats.items[0].title == "Alice"

    # Search in-chat messages
    res_msgs = await svc.search_messages_in_chat(chat_id=101, query="Hello")
    assert len(res_msgs) == 1
    assert "Hello" in res_msgs[0].text
