"""Chat and dialog management service."""

from typing import List, Optional, Tuple

from app.cache.cache_service import CacheService
from app.core.constants import DEFAULT_CHATS_PER_PAGE
from app.core.logging import get_logger
from app.database.repository import AuditRepository, ChatCacheRepository, FavoriteRepository
from app.database.session import get_db_session
from app.telegram.adapter import ChatDTO, ChatPermissionsDTO, TelegramClientAdapter
from app.utils.pagination import PaginatedResult, paginate_list

logger = get_logger(__name__)


class ChatService:
    """Orchestrates dialog fetching, unread tracking, favorites, and pagination."""

    def __init__(
        self,
        adapter: TelegramClientAdapter,
        cache_service: Optional[CacheService] = None,
    ) -> None:
        self.adapter = adapter
        self.cache = cache_service

    async def get_dialogs_paginated(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = DEFAULT_CHATS_PER_PAGE,
        favorites_only: bool = False,
    ) -> PaginatedResult[ChatDTO]:
        """Fetch dialogs from adapter, augment with DB favorites and cache, and paginate."""
        dialogs = await self.adapter.get_dialogs(limit=100)

        # Retrieve user favorites from DB
        async with get_db_session() as session:
            fav_repo = FavoriteRepository(session)
            cache_repo = ChatCacheRepository(session)
            favorite_ids = await fav_repo.get_favorite_chat_ids(user_id)

            # Update cached chat titles & marks
            for d in dialogs:
                d.is_favorite = (d.id in favorite_ids)
                await cache_repo.upsert_chat(
                    chat_id=d.id,
                    title=d.title,
                    chat_type=d.chat_type.value,
                    username=d.username,
                    unread_count=d.unread_count,
                )

        if favorites_only:
            dialogs = [d for d in dialogs if d.is_favorite]
        else:
            # Sort favorites to the top, then sort by unread count descending
            dialogs.sort(key=lambda d: (d.is_favorite, d.unread_count > 0), reverse=True)

        return paginate_list(dialogs, page=page, per_page=per_page)

    async def get_chat_details(
        self,
        user_id: int,
        chat_id: int,
    ) -> Tuple[ChatDTO, ChatPermissionsDTO]:
        """Fetch chat metadata and user's permissions in that chat."""
        chat_dto = await self.adapter.get_chat(chat_id)
        perms_dto = await self.adapter.get_permissions(chat_id)

        # Check favorite status
        async with get_db_session() as session:
            fav_repo = FavoriteRepository(session)
            chat_dto.is_favorite = await fav_repo.is_favorite(user_id, chat_id)

        return chat_dto, perms_dto

    async def toggle_favorite(
        self,
        user_id: int,
        chat_id: int,
    ) -> bool:
        """Toggle favorite bookmark for a chat. Returns True if now favorite, False if removed."""
        async with get_db_session() as session:
            fav_repo = FavoriteRepository(session)
            is_fav = await fav_repo.is_favorite(user_id, chat_id)

            if is_fav:
                await fav_repo.remove_favorite(user_id, chat_id)
                return False

            chat_dto = await self.adapter.get_chat(chat_id)
            await fav_repo.add_favorite(
                user_id=user_id,
                chat_id=chat_id,
                title=chat_dto.title,
                chat_type=chat_dto.chat_type.value,
                username=chat_dto.username,
            )
            return True

    async def resolve_and_get_chat(
        self,
        user_id: int,
        identifier: str | int,
    ) -> Tuple[ChatDTO, ChatPermissionsDTO]:
        """Resolve arbitrary Telegram username or ID and return metadata with user permissions."""
        chat_dto = await self.adapter.resolve_peer(identifier)
        perms_dto = await self.adapter.get_permissions(chat_dto.id)

        async with get_db_session() as session:
            fav_repo = FavoriteRepository(session)
            cache_repo = ChatCacheRepository(session)
            chat_dto.is_favorite = await fav_repo.is_favorite(user_id, chat_dto.id)
            await cache_repo.upsert_chat(
                chat_id=chat_dto.id,
                title=chat_dto.title,
                chat_type=chat_dto.chat_type.value,
                username=chat_dto.username,
                unread_count=chat_dto.unread_count,
            )

        return chat_dto, perms_dto

    async def join_channel(
        self,
        user_id: int,
        channel_id: int | str,
    ) -> ChatDTO:
        """Join a public channel on Telegram and record audit log."""
        chat_dto = await self.adapter.join_channel(channel_id)

        async with get_db_session() as session:
            audit = AuditRepository(session)
            await audit.log_action(
                user_id=user_id,
                action="JOIN_CHANNEL",
                chat_id=chat_dto.id,
                details=f"title={chat_dto.title}, username={chat_dto.username}",
            )

        logger.info(f"User {user_id} joined channel {chat_dto.id} ({chat_dto.title})")
        return chat_dto
