"""Search service for finding chats and messages."""

from typing import List

from app.telegram.adapter import ChatDTO, MessageDTO, TelegramClientAdapter
from app.utils.pagination import PaginatedResult, paginate_list


class SearchService:
    """Provides querying capabilities across dialogs and within chat message history."""

    def __init__(self, adapter: TelegramClientAdapter) -> None:
        self.adapter = adapter

    async def search_chats(
        self,
        query: str,
        page: int = 1,
        per_page: int = 6,
    ) -> PaginatedResult[ChatDTO]:
        """Search dialogs matching title or username."""
        clean_query = query.strip()
        if not clean_query:
            return paginate_list([], page=page, per_page=per_page)

        matched_chats = await self.adapter.search_dialogs(clean_query, limit=50)
        return paginate_list(matched_chats, page=page, per_page=per_page)

    async def search_messages_in_chat(
        self,
        chat_id: int,
        query: str,
        limit: int = 10,
    ) -> List[MessageDTO]:
        """Search messages within a specific chat."""
        clean_query = query.strip()
        if not clean_query:
            return []

        return await self.adapter.search_messages(
            chat_id=chat_id,
            query=clean_query,
            limit=limit,
        )
