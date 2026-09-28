"""Repository layer for async database CRUD operations."""

from datetime import datetime
from typing import Any, List, Optional, Set

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.models import AuditLog, CachedChat, FavoriteChat, UserSetting

logger = get_logger(__name__)


class UserRepository:
    """Repository managing user-specific settings."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_settings(self, user_id: int) -> UserSetting:
        """Fetch settings for a user, creating default settings if none exist."""
        stmt = select(UserSetting).where(UserSetting.user_id == user_id)
        result = await self.session.execute(stmt)
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSetting(
                user_id=user_id,
                notifications_enabled=True,
                notify_favorites_only=False,
                messages_per_page=10,
                auto_refresh=False,
            )
            self.session.add(settings)
            await self.session.flush()
            logger.info(f"Created initial settings for user_id={user_id}")

        return settings

    async def update_settings(self, user_id: int, **fields: Any) -> UserSetting:
        """Update specific settings fields for a user."""
        settings = await self.get_or_create_settings(user_id)
        for key, value in fields.items():
            if hasattr(settings, key) and key not in ("user_id", "created_at"):
                setattr(settings, key, value)
        await self.session.flush()
        return settings


class FavoriteRepository:
    """Repository managing bookmarked/favorite chats."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_favorites(self, user_id: int) -> List[FavoriteChat]:
        """Return all favorite chats bookmarked by a user."""
        stmt = select(FavoriteChat).where(FavoriteChat.user_id == user_id).order_by(FavoriteChat.title)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_favorite_chat_ids(self, user_id: int) -> Set[int]:
        """Return a set of chat IDs marked as favorite by the user."""
        stmt = select(FavoriteChat.chat_id).where(FavoriteChat.user_id == user_id)
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def is_favorite(self, user_id: int, chat_id: int) -> bool:
        """Check if a specific chat is in the user's favorites."""
        stmt = select(FavoriteChat.id).where(
            FavoriteChat.user_id == user_id,
            FavoriteChat.chat_id == chat_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_favorite(
        self,
        user_id: int,
        chat_id: int,
        title: str,
        chat_type: str,
        username: Optional[str] = None,
    ) -> FavoriteChat:
        """Add a chat to favorites or return existing bookmark."""
        stmt = select(FavoriteChat).where(
            FavoriteChat.user_id == user_id,
            FavoriteChat.chat_id == chat_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.title = title
            existing.username = username
            existing.chat_type = chat_type
            await self.session.flush()
            return existing

        fav = FavoriteChat(
            user_id=user_id,
            chat_id=chat_id,
            title=title,
            username=username,
            chat_type=chat_type,
        )
        self.session.add(fav)
        await self.session.flush()
        logger.info(f"User {user_id} added chat {chat_id} ('{title}') to favorites")
        return fav

    async def remove_favorite(self, user_id: int, chat_id: int) -> bool:
        """Remove a chat from user favorites. Returns True if removed."""
        stmt = delete(FavoriteChat).where(
            FavoriteChat.user_id == user_id,
            FavoriteChat.chat_id == chat_id,
        )
        result = await self.session.execute(stmt)
        deleted = (result.rowcount or 0) > 0
        if deleted:
            logger.info(f"User {user_id} removed chat {chat_id} from favorites")
        return deleted


class ChatCacheRepository:
    """Repository for cached chat titles, usernames, and unread counts."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_chat(
        self,
        chat_id: int,
        title: str,
        chat_type: str,
        username: Optional[str] = None,
        unread_count: int = 0,
    ) -> CachedChat:
        """Insert or update a single chat in the cache."""
        stmt = select(CachedChat).where(CachedChat.chat_id == chat_id)
        result = await self.session.execute(stmt)
        cached = result.scalar_one_or_none()

        if cached:
            cached.title = title
            cached.username = username
            cached.chat_type = chat_type
            cached.unread_count = unread_count
        else:
            cached = CachedChat(
                chat_id=chat_id,
                title=title,
                username=username,
                chat_type=chat_type,
                unread_count=unread_count,
            )
            self.session.add(cached)

        await self.session.flush()
        return cached

    async def get_cached_chat(self, chat_id: int) -> Optional[CachedChat]:
        """Retrieve a cached chat record by ID."""
        stmt = select(CachedChat).where(CachedChat.chat_id == chat_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_cached_chats(self, query: str, limit: int = 10) -> List[CachedChat]:
        """Search cached chats by title or username."""
        pattern = f"%{query}%"
        stmt = (
            select(CachedChat)
            .where(
                (CachedChat.title.ilike(pattern)) | (CachedChat.username.ilike(pattern))
            )
            .order_by(CachedChat.title)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AuditRepository:
    """Repository for security and audit trail logging."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_action(
        self,
        user_id: int,
        action: str,
        chat_id: Optional[int] = None,
        details: Optional[str] = None,
    ) -> AuditLog:
        """Record an action in the audit log."""
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            chat_id=chat_id,
            details=details,
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry
