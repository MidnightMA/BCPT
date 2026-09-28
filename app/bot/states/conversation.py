"""User-isolated state machine for managing multi-step bot interactions."""

import json
from typing import Any, Dict, Optional, Tuple

from app.cache.redis import CacheClient, get_cache
from app.core.constants import BotState
from app.core.logging import get_logger

logger = get_logger(__name__)


class StateManager:
    """
    Manages interactive state (e.g. waiting for message text, file upload, search query)
    scoped per authorized controller user ID.
    """

    def __init__(self, cache_client: CacheClient) -> None:
        self.cache = cache_client

    def _state_key(self, user_id: int) -> str:
        return f"bot:state:{user_id}"

    async def set_state(
        self,
        user_id: int,
        state: BotState,
        data: Optional[Dict[str, Any]] = None,
        ttl: int = 900,  # 15 minutes default state timeout
    ) -> None:
        """Set active interaction state and context payload for a user."""
        key = self._state_key(user_id)
        payload = {
            "state": state.value if isinstance(state, BotState) else str(state),
            "data": data or {},
        }
        await self.cache.set(key, json.dumps(payload), ttl=ttl)
        logger.debug(f"User {user_id} transitioned to state: {state} with data keys: {list((data or {}).keys())}")

    async def get_state(self, user_id: int) -> Tuple[BotState, Dict[str, Any]]:
        """Retrieve current state and associated payload for a user."""
        key = self._state_key(user_id)
        raw = await self.cache.get(key)
        if not raw:
            return BotState.IDLE, {}
        try:
            parsed = json.loads(raw)
            state_str = parsed.get("state", BotState.IDLE.value)
            state = BotState(state_str)
            data = parsed.get("data", {})
            return state, data
        except Exception as exc:
            logger.warning(f"Error parsing state for user {user_id}: {exc}. Resetting to IDLE.")
            await self.clear_state(user_id)
            return BotState.IDLE, {}

    async def clear_state(self, user_id: int) -> None:
        """Reset user state to IDLE and remove payload."""
        key = self._state_key(user_id)
        await self.cache.delete(key)
        logger.debug(f"User {user_id} state cleared to IDLE.")

    async def update_data(self, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        """Merge additional key/value pairs into the current user's state data."""
        state, data = await self.get_state(user_id)
        data.update(kwargs)
        await self.set_state(user_id, state, data)
        return data


_state_manager: Optional[StateManager] = None


async def get_state_manager() -> StateManager:
    """Return initialized global StateManager singleton."""
    global _state_manager
    if _state_manager is None:
        cache = await get_cache()
        _state_manager = StateManager(cache)
    return _state_manager
