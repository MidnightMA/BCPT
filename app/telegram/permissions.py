"""Chat permissions inspection and capability resolution."""

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

from app.core.constants import ChatType
from app.core.logging import get_logger
from app.telegram.adapter import ChatPermissionsDTO
from app.telegram.dialogs import determine_chat_type

logger = get_logger(__name__)


async def evaluate_permissions(client: TelegramClient, chat_id: int) -> ChatPermissionsDTO:
    """
    Inspect the user's role and granular rights in the chat.
    Distinguishes between private chats, groups, supergroups, and broadcast channels.
    """
    try:
        entity = await client.get_entity(chat_id)
        chat_type = determine_chat_type(entity)

        # 1. Private chats, bots, and saved messages have full individual rights
        if chat_type in (ChatType.USER, ChatType.BOT, ChatType.SAVED_MESSAGES):
            return ChatPermissionsDTO(
                can_send_messages=True,
                can_send_media=True,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                can_pin_messages=True,
                is_admin=True,
                is_creator=True,
            )

        # 2. Broadcast Channels
        if chat_type == ChatType.CHANNEL:
            is_creator = getattr(entity, "creator", False)
            admin_rights = getattr(entity, "admin_rights", None)
            is_admin = bool(is_creator or admin_rights)

            # In a broadcast channel, only admins with post rights can write
            can_post = is_creator or (admin_rights and getattr(admin_rights, "post_messages", False))
            can_edit = is_creator or (admin_rights and getattr(admin_rights, "edit_messages", False))
            can_delete = is_creator or (admin_rights and getattr(admin_rights, "delete_messages", False))
            can_pin = is_creator or (admin_rights and getattr(admin_rights, "pin_messages", False))

            return ChatPermissionsDTO(
                can_send_messages=bool(can_post),
                can_send_media=bool(can_post),
                can_post_messages=bool(can_post),
                can_edit_messages=bool(can_edit),
                can_delete_messages=bool(can_delete),
                can_pin_messages=bool(can_pin),
                is_admin=is_admin,
                is_creator=is_creator,
            )

        # 3. Groups & Supergroups
        try:
            perms = await client.get_permissions(entity, "me")
            is_creator = getattr(perms, "is_creator", False)
            is_admin = getattr(perms, "is_admin", False)

            can_send_msgs = getattr(perms, "send_messages", True)
            can_send_media = getattr(perms, "send_media", True)
            can_pin = getattr(perms, "pin_messages", is_admin)
            can_delete = is_admin or is_creator

            return ChatPermissionsDTO(
                can_send_messages=bool(can_send_msgs),
                can_send_media=bool(can_send_media),
                can_post_messages=bool(can_send_msgs),
                can_edit_messages=True,
                can_delete_messages=bool(can_delete),
                can_pin_messages=bool(can_pin),
                is_admin=is_admin,
                is_creator=is_creator,
            )
        except Exception as perm_err:
            logger.debug(f"Could not fetch granular permissions for chat {chat_id}: {perm_err}")
            # Fallback to entity-level defaults
            is_creator = getattr(entity, "creator", False)
            admin_rights = getattr(entity, "admin_rights", None)
            return ChatPermissionsDTO(
                can_send_messages=True,
                can_send_media=True,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=bool(is_creator or admin_rights),
                can_pin_messages=bool(is_creator or admin_rights),
                is_admin=bool(admin_rights or is_creator),
                is_creator=is_creator,
            )

    except Exception as exc:
        logger.warning(f"Error evaluating permissions for chat {chat_id}: {exc}")
        # Safe default: read-only until confirmed
        return ChatPermissionsDTO(
            can_send_messages=True,
            can_send_media=True,
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=False,
            can_pin_messages=False,
            is_admin=False,
            is_creator=False,
        )
