"""Telethon client lifecycle manager and MTProto error boundary."""

import asyncio
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from app.core.config import get_settings
from app.core.exceptions import (
    ChannelJoinError,
    ChatNotFoundError,
    ConnectionFailedError,
    FloodWaitError,
    PeerNotFoundError,
    PermissionDeniedError,
    TelegramClientError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class TelethonClientManager:
    """Manages the lifecycle, connectivity, and MTProto sessions of the Telethon client."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_path: str,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = session_path
        self._client: Optional[TelegramClient] = None
        self._lock = asyncio.Lock()

    @property
    def raw_client(self) -> TelegramClient:
        """Access raw Telethon client (for internal adapter use only)."""
        if self._client is None:
            raise ConnectionFailedError("Telethon client has not been initialized.")
        return self._client

    def is_connected(self) -> bool:
        """Check if client exists and is connected."""
        return self._client is not None and self._client.is_connected()

    async def connect(self) -> TelegramClient:
        """Initialize and connect the Telethon client."""
        async with self._lock:
            if self._client is not None and self._client.is_connected():
                return self._client

            logger.info("Initializing Telethon client...")
            # Ensure parent session directory exists
            Path(self.session_path).parent.mkdir(parents=True, exist_ok=True)

            self._client = TelegramClient(
                session=self.session_path,
                api_id=self.api_id,
                api_hash=self.api_hash,
                auto_reconnect=True,
                connection_retries=10,
                retry_delay=3,
                flood_sleep_threshold=0,  # Central throttler manages FloodWait explicitly
            )

            try:
                await self._client.connect()
                if not await self._client.is_user_authorized():
                    logger.warning(
                        "Telethon session exists but is NOT authorized! "
                        "Please run setup_telethon.py to authenticate your account."
                    )
                else:
                    me = await self._client.get_me()
                    logger.info(f"Telethon connected as: {getattr(me, 'first_name', '')} (ID: {getattr(me, 'id', '')})")
                return self._client
            except errors.FloodWaitError as exc:
                logger.error(f"Telethon FloodWait on connect: {exc.seconds}s")
                raise FloodWaitError(exc.seconds) from exc
            except Exception as exc:
                logger.error(f"Failed to connect Telethon: {exc}", exc_info=True)
                raise ConnectionFailedError(f"Failed to connect Telethon: {exc}") from exc

    async def ensure_connected(self) -> TelegramClient:
        """Ensure Telethon is active and connected, reconnecting if disconnected."""
        if self._client is not None and self._client.is_connected():
            return self._client
        return await self.connect()

    async def disconnect(self) -> None:
        """Cleanly disconnect Telethon client."""
        async with self._lock:
            if self._client is not None:
                logger.info("Disconnecting Telethon client...")
                try:
                    await self._client.disconnect()
                except Exception as exc:
                    logger.warning(f"Error during Telethon disconnect: {exc}")
                finally:
                    self._client = None
                logger.info("Telethon client disconnected.")


def map_telethon_error(exc: Exception) -> Exception:
    """Map raw Telethon exceptions to domain-specific application exceptions."""
    if isinstance(exc, errors.FloodWaitError):
        return FloodWaitError(seconds=exc.seconds)
    if isinstance(exc, (errors.UserBannedInChannelError, errors.ChatAdminRequiredError, errors.ChatWriteForbiddenError)):
        return PermissionDeniedError(action="perform this action", message=str(exc))
    if isinstance(exc, (errors.UsernameNotOccupiedError, errors.UsernameInvalidError)):
        return PeerNotFoundError(identifier="Target", message=str(exc))
    if isinstance(exc, errors.ChannelPrivateError):
        return PeerNotFoundError(identifier="Target", message="This channel or chat is private or inaccessible.")
    if isinstance(exc, (errors.ChannelsTooMuchError, errors.ChannelInvalidError)):
        return ChannelJoinError(message=str(exc))
    if isinstance(exc, (errors.ChatIdInvalidError, errors.PeerIdInvalidError, ValueError)):
        return ChatNotFoundError(chat_id="Unknown", message=str(exc))
    if isinstance(exc, errors.RPCError):
        return TelegramClientError(message=f"Telegram RPC Error ({exc.code}): {exc.message}")
    return exc


_client_manager: Optional[TelethonClientManager] = None


def get_client_manager() -> TelethonClientManager:
    """Return singleton TelethonClientManager."""
    global _client_manager
    if _client_manager is None:
        settings = get_settings()
        _client_manager = TelethonClientManager(
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            session_path=settings.TELEGRAM_SESSION,
        )
    return _client_manager
