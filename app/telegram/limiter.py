"""Centralized async rate limiter, throttler, concurrency guard, and circuit breaker for Telethon."""

import asyncio
from math import ceil
import random
import time
from typing import Any, Callable, Coroutine, Dict, Optional, Set, Tuple

from telethon import errors as telethon_errors

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    CircuitBreakerOpenError,
    FloodWaitError,
    RequestQueueFullError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """Three-state (CLOSED, OPEN, HALF_OPEN) circuit breaker protecting against cascading Telegram errors."""

    def __init__(self, failure_threshold: int = 5, cooldown: float = 30.0) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown = max(1.0, cooldown)
        self._failures = 0
        self._last_failure_time = 0.0
        self._state = "CLOSED"
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    async def can_execute(self) -> Tuple[bool, float]:
        """Check if an execution is permitted. Returns (is_allowed, cooldown_remaining_seconds)."""
        async with self._lock:
            now = time.monotonic()
            if self._state == "OPEN":
                elapsed = now - self._last_failure_time
                if elapsed >= self.cooldown:
                    logger.info("Circuit breaker cooldown expired; entering HALF_OPEN probe state.")
                    self._state = "HALF_OPEN"
                    return True, 0.0
                return False, self.cooldown - elapsed
            return True, 0.0

    async def record_success(self) -> None:
        """Record successful call, recovering circuit to CLOSED."""
        async with self._lock:
            if self._failures > 0 or self._state != "CLOSED":
                logger.info(f"Circuit breaker recovered from state '{self._state}' to CLOSED.")
            self._failures = 0
            self._state = "CLOSED"

    async def record_failure(self) -> None:
        """Record failure, potentially tripping circuit to OPEN."""
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.monotonic()
            if self._state == "HALF_OPEN" or self._failures >= self.failure_threshold:
                self._state = "OPEN"
                logger.error(
                    f"Circuit breaker TRIPPED to OPEN ({self._failures} failures). "
                    f"Rejecting requests for {self.cooldown}s."
                )

    async def reset(self) -> None:
        """Explicitly reset circuit breaker state."""
        async with self._lock:
            self._failures = 0
            self._state = "CLOSED"
            self._last_failure_time = 0.0


class RequestDeduplicator:
    """In-flight request coalescer and short-window debouncer for repeated UI interactions."""

    def __init__(self) -> None:
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._recent_results: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        key: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        debounce_window: float = 0.0,
    ) -> Any:
        """
        Deduplicate or coalesce identical async requests.
        - If debounce_window > 0 and recent cached result exists, returns cached result.
        - If an identical request is already running in-flight, awaits and returns that result.
        """
        future_to_await: Optional[asyncio.Future] = None
        is_initiator = False

        async with self._lock:
            # 1. Debounce check
            now = time.monotonic()
            if debounce_window > 0 and key in self._recent_results:
                val, expiry = self._recent_results[key]
                if now < expiry:
                    logger.debug(f"Debounce hit for action '{key}'; reusing recent result.")
                    return val
                del self._recent_results[key]

            # 2. In-flight coalescing check
            if key in self._in_flight:
                logger.debug(f"Coalescing duplicate in-flight request for '{key}'.")
                future_to_await = self._in_flight[key]
            else:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                self._in_flight[key] = future
                is_initiator = True

        if not is_initiator and future_to_await is not None:
            return await future_to_await

        # Initiator executes the actual operation
        try:
            result = await coro_fn()
            async with self._lock:
                fut = self._in_flight.pop(key, None)
                if fut and not fut.done():
                    fut.set_result(result)
                if debounce_window > 0:
                    self._recent_results[key] = (result, time.monotonic() + debounce_window)
            return result
        except Exception as exc:
            async with self._lock:
                fut = self._in_flight.pop(key, None)
                if fut and not fut.done():
                    fut.set_exception(exc)
            raise

    async def clear(self) -> None:
        """Clear all deduplication and debounce state."""
        async with self._lock:
            self._in_flight.clear()
            self._recent_results.clear()


class TelegramThrottler:
    """
    Centralized coordinator for all Telethon operations:
    - Global token / rate limiting
    - Per-chat request pacing
    - Controlled concurrency (general & media semaphores)
    - Bounded pending queue limit
    - FloodWait compliance and safe backoff
    - Transient retry with exponential backoff and random jitter
    - Circuit breaker safety shutoff
    - Request deduplication and debouncing
    """

    # Errors classified as transient network/server glitches eligible for retry
    _TRANSIENT_ERRORS: Tuple[type[Exception], ...] = (
        ConnectionError,
        asyncio.TimeoutError,
        OSError,
        telethon_errors.RpcCallFailError,
        telethon_errors.TimedOutError,
        telethon_errors.ServerError,
    )

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.TELEGRAM_CIRCUIT_BREAKER_FAILURES,
            cooldown=self.settings.TELEGRAM_CIRCUIT_BREAKER_COOLDOWN,
        )
        self.deduplicator = RequestDeduplicator()

        self._global_semaphore = asyncio.Semaphore(self.settings.TELEGRAM_MAX_CONCURRENT_REQUESTS)
        self._media_semaphore = asyncio.Semaphore(self.settings.TELEGRAM_MAX_CONCURRENT_MEDIA)

        self._queue_lock = asyncio.Lock()
        self._queue_size = 0

        self._global_rate_lock = asyncio.Lock()
        self._last_global_call_time = 0.0

        self._chat_locks: Dict[int, asyncio.Lock] = {}
        self._chat_locks_guard = asyncio.Lock()
        self._last_chat_call_time: Dict[int, float] = {}

        self._global_flood_wait_until = 0.0
        self._chat_flood_wait_until: Dict[int, float] = {}

    @property
    def queue_size(self) -> int:
        return self._queue_size

    async def _get_chat_lock(self, chat_id: int) -> asyncio.Lock:
        async with self._chat_locks_guard:
            if chat_id not in self._chat_locks:
                self._chat_locks[chat_id] = asyncio.Lock()
            return self._chat_locks[chat_id]

    async def execute(
        self,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        chat_id: Optional[int] = None,
        is_media: bool = False,
        dedup_key: Optional[str] = None,
        debounce_window: float = 0.0,
    ) -> Any:
        """
        Execute an MTProto operation safely through rate limiting, concurrency,
        queue bounding, circuit breaker, FloodWait, and retry guards.
        """
        if dedup_key:
            return await self.deduplicator.execute(
                key=dedup_key,
                coro_fn=lambda: self._execute_internal(coro_fn, chat_id=chat_id, is_media=is_media),
                debounce_window=debounce_window,
            )
        return await self._execute_internal(coro_fn, chat_id=chat_id, is_media=is_media)

    async def _execute_internal(
        self,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        chat_id: Optional[int] = None,
        is_media: bool = False,
    ) -> Any:
        # 1. Bounded queue check
        async with self._queue_lock:
            if self._queue_size >= self.settings.TELEGRAM_REQUEST_QUEUE_MAX_SIZE:
                logger.warning(f"Rejecting request: queue limit reached ({self._queue_size}).")
                raise RequestQueueFullError()
            self._queue_size += 1

        try:
            # 2. Circuit breaker check
            can_exec, remaining = await self.circuit_breaker.can_execute()
            if not can_exec:
                raise CircuitBreakerOpenError(cooldown_remaining=remaining)

            # 3. Active FloodWait check
            now = time.monotonic()
            if now < self._global_flood_wait_until:
                wait_s = max(1, int(ceil(self._global_flood_wait_until - now)))
                raise FloodWaitError(
                    seconds=wait_s,
                    message=f"Global FloodWait in progress for another {wait_s}s.",
                )
            if chat_id and now < self._chat_flood_wait_until.get(chat_id, 0):
                wait_s = max(1, int(ceil(self._chat_flood_wait_until[chat_id] - now)))
                raise FloodWaitError(
                    seconds=wait_s,
                    message=f"Per-chat FloodWait active for chat {chat_id} ({wait_s}s remaining).",
                )

            # 4. Controlled concurrency acquisition
            async with self._global_semaphore:
                if is_media:
                    async with self._media_semaphore:
                        return await self._execute_with_throttling(coro_fn, chat_id)
                else:
                    return await self._execute_with_throttling(coro_fn, chat_id)

        finally:
            async with self._queue_lock:
                self._queue_size -= 1

    async def _execute_with_throttling(
        self,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        chat_id: Optional[int],
    ) -> Any:
        # 5. Global rate limiter spacing
        min_global_interval = 1.0 / max(0.1, self.settings.TELEGRAM_RATE_LIMIT_GLOBAL)
        async with self._global_rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_global_call_time
            if elapsed < min_global_interval:
                sleep_time = min_global_interval - elapsed
                await asyncio.sleep(sleep_time)
            self._last_global_call_time = time.monotonic()

        # 6. Per-chat throttling
        if chat_id is not None:
            chat_lock = await self._get_chat_lock(chat_id)
            async with chat_lock:
                now = time.monotonic()
                elapsed = now - self._last_chat_call_time.get(chat_id, 0.0)
                if elapsed < self.settings.TELEGRAM_PER_CHAT_RATE_LIMIT:
                    sleep_time = self.settings.TELEGRAM_PER_CHAT_RATE_LIMIT - elapsed
                    await asyncio.sleep(sleep_time)
                self._last_chat_call_time[chat_id] = time.monotonic()
                return await self._run_with_retries(coro_fn, chat_id)

        return await self._run_with_retries(coro_fn, None)

    async def _run_with_retries(
        self,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        chat_id: Optional[int],
    ) -> Any:
        """Run callable with FloodWait detection, transient retries, and circuit breaker recording."""
        attempt = 0
        while True:
            try:
                result = await coro_fn()
                await self.circuit_breaker.record_success()
                return result

            except telethon_errors.FloodWaitError as exc:
                wait_seconds = int(exc.seconds)
                deadline = time.monotonic() + wait_seconds
                if chat_id is not None:
                    self._chat_flood_wait_until[chat_id] = deadline
                else:
                    self._global_flood_wait_until = deadline

                # Never retry before Telegram's required wait time!
                if wait_seconds <= self.settings.TELEGRAM_AUTO_FLOOD_WAIT_MAX:
                    logger.warning(
                        f"FloodWaitError: Telegram required wait of {wait_seconds}s "
                        f"is within auto-wait limit ({self.settings.TELEGRAM_AUTO_FLOOD_WAIT_MAX}s). "
                        f"Sleeping {wait_seconds + 0.5:.1f}s before retrying..."
                    )
                    await asyncio.sleep(wait_seconds + 0.5)
                    # Retry once after required wait
                    try:
                        result = await coro_fn()
                        await self.circuit_breaker.record_success()
                        return result
                    except Exception as retry_exc:
                        await self.circuit_breaker.record_failure()
                        raise
                else:
                    logger.error(
                        f"FloodWaitError: Telegram required wait of {wait_seconds}s "
                        f"exceeds auto-wait limit ({self.settings.TELEGRAM_AUTO_FLOOD_WAIT_MAX}s). Failing fast."
                    )
                    await self.circuit_breaker.record_failure()
                    raise FloodWaitError(seconds=wait_seconds) from exc

            except self._TRANSIENT_ERRORS as exc:
                attempt += 1
                if attempt <= self.settings.TELEGRAM_MAX_RETRIES:
                    base = self.settings.TELEGRAM_RETRY_BASE_DELAY
                    max_d = self.settings.TELEGRAM_RETRY_MAX_DELAY
                    jitter = random.uniform(0, max(0.01, self.settings.TELEGRAM_RETRY_JITTER))
                    delay = min(max_d, base * (2 ** (attempt - 1))) + jitter
                    logger.warning(
                        f"Transient error ({type(exc).__name__}: {exc}). "
                        f"Retrying attempt {attempt}/{self.settings.TELEGRAM_MAX_RETRIES} in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(f"Exhausted {self.settings.TELEGRAM_MAX_RETRIES} retries for transient error: {exc}")
                await self.circuit_breaker.record_failure()
                raise

            except Exception as exc:
                if isinstance(exc, (telethon_errors.RPCError, telethon_errors.ServerError)):
                    await self.circuit_breaker.record_failure()
                raise


_global_throttler: Optional[TelegramThrottler] = None


def get_telegram_throttler() -> TelegramThrottler:
    """Return singleton TelegramThrottler."""
    global _global_throttler
    if _global_throttler is None:
        _global_throttler = TelegramThrottler()
    return _global_throttler
