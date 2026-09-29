"""Telethon dialog and chat fetching implementation."""

from datetime import datetime
import re
from typing import List, Optional

from telethon import TelegramClient
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Channel, Chat, User

from app.core.constants import ChatType
from app.telegram.adapter import ChatDTO


def determine_chat_type(entity: object) -> ChatType:
    """Classify a Telethon entity into domain ChatType."""
    if isinstance(entity, User):
        if getattr(entity, "is_self", False):
            return ChatType.SAVED_MESSAGES
        if getattr(entity, "bot", False):
            return ChatType.BOT
        return ChatType.USER
    if isinstance(entity, Chat):
        return ChatType.GROUP
    if isinstance(entity, Channel):
        if getattr(entity, "broadcast", False):
            return ChatType.CHANNEL
        return ChatType.SUPERGROUP
    return ChatType.GROUP


def entity_to_chat_dto(entity: object, unread_count: int = 0) -> ChatDTO:
    """Convert a Telethon entity or dialog into a domain ChatDTO."""
    chat_type = determine_chat_type(entity)
    title = getattr(entity, "title", None)
    if not title:
        first = getattr(entity, "first_name", "") or ""
        last = getattr(entity, "last_name", "") or ""
        title = f"{first} {last}".strip() or "Unnamed Chat"

    username = getattr(entity, "username", None)
    chat_id = getattr(entity, "id", 0)
    participants = getattr(entity, "participants_count", None)
    is_restricted = getattr(entity, "restricted", False)

    return ChatDTO(
        id=chat_id,
        title=title,
        chat_type=chat_type,
        username=username,
        unread_count=unread_count,
        participants_count=participants,
        is_restricted=is_restricted,
    )


async def fetch_dialogs(
    client: TelegramClient,
    limit: int = 50,
    offset_date: Optional[datetime] = None,
    offset_id: int = 0,
) -> List[ChatDTO]:
    """Retrieve user dialogs and map them to ChatDTOs."""
    dialogs = await client.get_dialogs(
        limit=limit,
        offset_date=offset_date,
        offset_id=offset_id,
    )

    result: List[ChatDTO] = []
    for d in dialogs:
        dto = entity_to_chat_dto(d.entity, unread_count=getattr(d, "unread_count", 0))
        result.append(dto)
    return result


async def fetch_chat(client: TelegramClient, chat_id: int) -> ChatDTO:
    """Retrieve a single chat entity by ID and convert to ChatDTO."""
    entity = await client.get_entity(chat_id)
    return entity_to_chat_dto(entity)


def normalize_peer_identifier(identifier: str | int) -> str | int:
    """Clean and normalize a Telegram peer identifier (URL, username, phone, or numeric ID)."""
    if isinstance(identifier, int):
        return identifier

    clean = str(identifier).strip()
    # Strip t.me URL patterns: https://t.me/username, http://t.me/username, t.me/username
    clean = re.sub(r"^(https?:\/\/)?(www\.)?t\.me\/", "", clean)
    clean = clean.strip("/")

    # Strip leading @
    if clean.startswith("@"):
        clean = clean[1:]

    # Check if purely numeric ID (e.g. 12345678 or -1001234567890)
    if clean.lstrip("-").isdigit():
        try:
            return int(clean)
        except ValueError:
            pass

    return clean


async def resolve_peer_entity(client: TelegramClient, identifier: str | int) -> ChatDTO:
    """Resolve an arbitrary username, link, or ID via Telethon and map to ChatDTO."""
    norm_id = normalize_peer_identifier(identifier)
    entity = await client.get_entity(norm_id)
    return entity_to_chat_dto(entity)


async def join_channel_entity(client: TelegramClient, channel_id: int | str) -> ChatDTO:
    """Join a public Telegram channel by ID or username."""
    norm_id = normalize_peer_identifier(channel_id)
    entity = await client.get_entity(norm_id)
    try:
        await client(JoinChannelRequest(entity))
    except UserAlreadyParticipantError:
        pass

    # Refetch entity to get updated participant status/counts
    updated_entity = await client.get_entity(entity.id)
    return entity_to_chat_dto(updated_entity)
