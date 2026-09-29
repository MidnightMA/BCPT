"""Tests for business services (Chat, Message, Media, and Search)."""

from pathlib import Path

import pytest

from app.core.constants import ChatType, MessageType
from app.core.exceptions import MessageNotFoundError, PeerNotFoundError
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


@pytest.mark.asyncio
async def test_chat_service_resolve_peer(mock_adapter, mock_settings):
    """Verify resolving both private user and public channel entities."""
    svc = ChatService(mock_adapter)
    user_id = 111222333

    # 1. Resolve private user (never contacted before)
    chat_dto, perms = await svc.resolve_and_get_chat(user_id, "@newuser")
    assert chat_dto.id == 888
    assert chat_dto.chat_type == ChatType.USER
    assert chat_dto.username == "newuser"

    # 2. Resolve public channel
    chan_dto, chan_perms = await svc.resolve_and_get_chat(user_id, "t.me/newchan")
    assert chan_dto.id == 9999
    assert chan_dto.chat_type == ChatType.CHANNEL

    # 3. Nonexistent peer raises PeerNotFoundError
    with pytest.raises(PeerNotFoundError):
        await svc.resolve_and_get_chat(user_id, "@nonexistent")


@pytest.mark.asyncio
async def test_chat_service_join_channel(mock_adapter, mock_settings):
    """Verify joining a public channel."""
    svc = ChatService(mock_adapter)
    user_id = 111222333

    joined = await svc.join_channel(user_id, "303")
    assert joined.id == 303
    assert joined.chat_type == ChatType.CHANNEL


@pytest.mark.asyncio
async def test_message_service_get_message_and_media(mock_adapter, mock_settings, tmp_path):
    """Verify retrieving full message and downloading media."""
    svc = MessageService(mock_adapter)

    # 1. Get existing message
    msg = await svc.get_message(chat_id=101, message_id=1)
    assert msg.id == 1
    assert msg.text == "Hello there!"

    # 2. Nonexistent message raises MessageNotFoundError
    with pytest.raises(MessageNotFoundError):
        await svc.get_message(chat_id=101, message_id=99999)

    # 3. Add message with media to mock adapter
    from datetime import datetime, timezone
    mock_adapter.messages.append(
        MessageDTO(
            id=3,
            chat_id=101,
            sender_id=101,
            sender_name="Alice",
            is_outgoing=False,
            text="Look at this photo",
            date=datetime.now(timezone.utc),
            media_type=MessageType.PHOTO,
            media_filename="photo.jpg",
            media_size=1024,
            grouped_id=55555,
        )
    )

    # Download media items (returns album items)
    media_items = await svc.download_message_media(chat_id=101, message_id=3, temp_dir=str(tmp_path))
    assert len(media_items) == 2
    assert media_items[0].file_path.exists()
    assert media_items[1].file_path.exists()
    assert media_items[0].media_type == MessageType.PHOTO
