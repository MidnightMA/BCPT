"""Pytest configuration, fixtures, and mocked adapter interfaces."""

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.cache.redis import CacheClient
from app.core.config import Settings
from app.core.constants import ChatType, MessageType
from app.database.models import Base
from app.telegram.adapter import (
    ChatDTO,
    ChatPermissionsDTO,
    MessageDTO,
    TelegramClientAdapter,
    UserDTO,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings(monkeypatch, tmp_path) -> Settings:
    """Provide isolated test settings."""
    temp_dir = tmp_path / "tmp"
    data_dir = tmp_path / "data"
    temp_dir.mkdir()
    data_dir.mkdir()

    settings = Settings(
        BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
        API_ID=123456,
        API_HASH="0123456789abcdef0123456789abcdef",
        TELEGRAM_SESSION=str(data_dir / "test.session"),
        AUTHORIZED_USER_IDS=[111222333, 999888777],
        DATABASE_URL=f"sqlite+aiosqlite:///{data_dir}/test.db",
        TEMP_DIR=str(temp_dir),
        DATA_DIR=str(data_dir),
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    return settings


@pytest_asyncio.fixture
async def db_session(tmp_path) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated, clean SQLite async database session."""
    db_path = tmp_path / "test_run.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def memory_cache() -> CacheClient:
    """Provide an in-memory cache client."""
    client = CacheClient(redis_url=None)
    await client.initialize()
    return client


class MockTelegramAdapter(TelegramClientAdapter):
    """Controllable mock of the Telegram client adapter for testing without MTProto network."""

    def __init__(self) -> None:
        self.connected = True
        self.dialogs: List[ChatDTO] = [
            ChatDTO(id=101, title="Alice", chat_type=ChatType.USER, unread_count=2),
            ChatDTO(id=202, title="Work Dev Group", chat_type=ChatType.GROUP, unread_count=5),
            ChatDTO(id=303, title="News Channel", chat_type=ChatType.CHANNEL, unread_count=0),
        ]
        self.messages: List[MessageDTO] = [
            MessageDTO(
                id=1,
                chat_id=101,
                sender_id=101,
                sender_name="Alice",
                is_outgoing=False,
                text="Hello there!",
                date=datetime.now(timezone.utc),
            ),
            MessageDTO(
                id=2,
                chat_id=101,
                sender_id=999,
                sender_name="You",
                is_outgoing=True,
                text="Hi Alice!",
                date=datetime.now(timezone.utc),
            ),
        ]
        self.permissions: ChatPermissionsDTO = ChatPermissionsDTO()

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    async def get_current_user(self) -> UserDTO:
        return UserDTO(id=999, first_name="Owner", username="owner_tg")

    async def get_dialogs(
        self,
        limit: int = 50,
        offset_date: Optional[datetime] = None,
        offset_id: int = 0,
    ) -> List[ChatDTO]:
        return self.dialogs[:limit]

    async def get_chat(self, chat_id: int) -> ChatDTO:
        for d in self.dialogs:
            if d.id == chat_id:
                return d
        return ChatDTO(id=chat_id, title=f"Chat {chat_id}", chat_type=ChatType.GROUP)

    async def get_messages(
        self,
        chat_id: int,
        limit: int = 10,
        offset_id: int = 0,
    ) -> List[MessageDTO]:
        return [m for m in self.messages if m.chat_id == chat_id][:limit]

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        new_id = len(self.messages) + 1
        msg = MessageDTO(
            id=new_id,
            chat_id=chat_id,
            sender_id=999,
            sender_name="You",
            is_outgoing=True,
            text=text,
            date=datetime.now(timezone.utc),
            reply_to_msg_id=reply_to_msg_id,
        )
        self.messages.append(msg)
        return msg

    async def send_file(
        self,
        chat_id: int,
        file_path: str,
        caption: Optional[str] = None,
        reply_to_msg_id: Optional[int] = None,
    ) -> MessageDTO:
        new_id = len(self.messages) + 1
        msg = MessageDTO(
            id=new_id,
            chat_id=chat_id,
            sender_id=999,
            sender_name="You",
            is_outgoing=True,
            text=caption or "",
            date=datetime.now(timezone.utc),
            media_type=MessageType.DOCUMENT,
            media_filename="file.pdf",
            reply_to_msg_id=reply_to_msg_id,
        )
        self.messages.append(msg)
        return msg

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> MessageDTO:
        for m in self.messages:
            if m.id == message_id:
                m.text = text
                return m
        raise ValueError(f"Message {message_id} not found")

    async def delete_message(
        self,
        chat_id: int,
        message_ids: List[int],
        revoke: bool = True,
    ) -> bool:
        self.messages = [m for m in self.messages if m.id not in message_ids]
        return True

    async def pin_message(
        self,
        chat_id: int,
        message_id: int,
        notify: bool = False,
    ) -> bool:
        return True

    async def get_permissions(self, chat_id: int) -> ChatPermissionsDTO:
        return self.permissions

    async def search_messages(
        self,
        chat_id: int,
        query: str,
        limit: int = 10,
    ) -> List[MessageDTO]:
        return [m for m in self.messages if query.lower() in m.text.lower()][:limit]

    async def search_dialogs(
        self,
        query: str,
        limit: int = 20,
    ) -> List[ChatDTO]:
        return [d for d in self.dialogs if query.lower() in d.title.lower()][:limit]


@pytest.fixture
def mock_adapter() -> MockTelegramAdapter:
    return MockTelegramAdapter()
