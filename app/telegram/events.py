"""Telethon MTProto event listeners and notification bridging."""

from telethon import events

from app.core.logging import get_logger
from app.telegram.client import TelethonClientManager
from app.telegram.messages import telethon_message_to_dto

logger = get_logger(__name__)


def setup_telethon_events(
    manager: TelethonClientManager,
    notification_dispatcher: object,
) -> None:
    """Register event handlers on the Telethon client."""
    client = manager.raw_client

    @client.on(events.NewMessage(incoming=True))
    async def on_new_message(event: events.NewMessage.Event) -> None:
        try:
            chat_id = event.chat_id
            if not chat_id:
                return

            msg_dto = telethon_message_to_dto(event.message, chat_id)

            # Dispatch asynchronously to notification service
            if hasattr(notification_dispatcher, "handle_new_message"):
                await notification_dispatcher.handle_new_message(msg_dto)

        except Exception as exc:
            logger.debug(f"Error processing Telethon incoming event: {exc}")

    logger.info("Registered Telethon MTProto event handlers.")
