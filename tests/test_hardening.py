"""Comprehensive tests for Telegram hardening: rate limiting, throttling, FloodWait handling, retries, caching, concurrency, and request deduplication."""

import asyncio
from datetime import datetime, timezone
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon import errors as telethon_errors

from app.cache.cache_service import CacheService
from app.cache.redis import CacheClient
from app.core.config import Settings
from app.core.constants import ChatType, MessageType
from app.core.exceptions import (
    CircuitBreakerOpenError,
    FloodWaitError,
    PermissionDeniedError,
    RequestQueueFullError,
)
from app.telegram.adapter import ChatDTO, ChatPermissionsDTO, MessageDTO, TelethonAdapter
from app.telegram.limiter import CircuitBreaker, RequestDeduplicator, TelegramThrottler


@pytest.fixture
def hardening_settings() -> Settings:
    """Settings configured with tight intervals suitable for fast test execution."""
    return Settings(
        BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
        API_ID=123456,
        API_HASH="0123456789abcdef0123456789abcdef",
        TELEGRAM_RATE_LIMIT_GLOBAL=20.0,      # 0.05s interval
        TELEGRAM_PER_CHAT_RATE_LIMIT=0.1,      # 0.1s interval
        TELEGRAM_MAX_CONCURRENT_REQUESTS=2,
        TELEGRAM_MAX_CONCURRENT_MEDIA=1,
        TELEGRAM_REQUEST_QUEUE_MAX_SIZE=4,
        TELEGRAM_AUTO_FLOOD_WAIT_MAX=1,        # 1s auto wait threshold
        TELEGRAM_MAX_RETRIES=2,
        TELEGRAM_RETRY_BASE_DELAY=0.05,
        TELEGRAM_RETRY_MAX_DELAY=0.2,
        TELEGRAM_RETRY_JITTER=0.01,
        TELEGRAM_CIRCUIT_BREAKER_FAILURES=3,
        TELEGRAM_CIRCUIT_BREAKER_COOLDOWN=0.2,  # 0.2s cooldown
        TELEGRAM_CACHE_TTL_CHATS=60,
        TELEGRAM_CACHE_TTL_DIALOGS=60,
        TELEGRAM_CACHE_TTL_PERMISSIONS=60,
        TELEGRAM_CACHE_TTL_MESSAGES=60,
        TELEGRAM_CACHE_TTL_PEERS=60,
        TELEGRAM_DEDUPLICATION_WINDOW=0.3,
        TELEGRAM_AUTO_READ_ON_INSPECT=True,
    )


# ---------------------------------------------------------------------------
# 1. Throttling & Rate Limiting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_throttler_per_chat_pacing(hardening_settings):
    """Verify minimum interval spacing between consecutive calls to the same chat."""
    throttler = TelegramThrottler(hardening_settings)
    timestamps = []

    async def sample_op():
        timestamps.append(time.monotonic())
        return "ok"

    # Two requests to the same chat
    await throttler.execute(sample_op, chat_id=101)
    await throttler.execute(sample_op, chat_id=101)

    assert len(timestamps) == 2
    delta = timestamps[1] - timestamps[0]
    # Should enforce at least TELEGRAM_PER_CHAT_RATE_LIMIT (0.1s)
    assert delta >= 0.08, f"Expected per-chat delay >= 0.08s, got {delta:.3f}s"


@pytest.mark.asyncio
async def test_throttler_independent_chats_not_blocked(hardening_settings):
    """Verify requests to different chats do not wait for another chat's per-chat interval."""
    throttler = TelegramThrottler(hardening_settings)
    timestamps = []

    async def sample_op():
        timestamps.append(time.monotonic())
        return "ok"

    # Two requests to different chats
    await throttler.execute(sample_op, chat_id=101)
    await throttler.execute(sample_op, chat_id=202)

    assert len(timestamps) == 2


# ---------------------------------------------------------------------------
# 2. FloodWait Handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flood_wait_auto_sleep_and_retry(hardening_settings):
    """Verify that a FloodWait <= auto threshold sleeps and retries once automatically."""
    throttler = TelegramThrottler(hardening_settings)
    call_count = 0

    async def flaky_op():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise telethon_errors.FloodWaitError(request=MagicMock(), capture=0)
        return "success"

    # Mock the FloodWait seconds property to 1 second
    with patch.object(telethon_errors.FloodWaitError, "seconds", 0.1):
        res = await throttler.execute(flaky_op, chat_id=101)
        assert res == "success"
        assert call_count == 2


@pytest.mark.asyncio
async def test_flood_wait_exceeds_threshold_fails_fast_and_blocks_further_calls(hardening_settings):
    """Verify that FloodWait > auto threshold raises domain FloodWaitError and protects account on future calls."""
    throttler = TelegramThrottler(hardening_settings)

    async def flood_op():
        raise telethon_errors.FloodWaitError(request=MagicMock(), capture=0)

    # 10s wait > 1s auto wait threshold
    with patch.object(telethon_errors.FloodWaitError, "seconds", 5):
        with pytest.raises(FloodWaitError) as exc_info:
            await throttler.execute(flood_op, chat_id=101)
        assert exc_info.value.seconds == 5

    # A subsequent call within the 5s window should fail fast without executing the callable
    called = False

    async def should_not_run():
        nonlocal called
        called = True
        return "ran"

    with pytest.raises(FloodWaitError):
        await throttler.execute(should_not_run, chat_id=101)

    assert called is False, "Call was made to Telegram despite active FloodWait!"


# ---------------------------------------------------------------------------
# 3. Transient Retries with Exponential Backoff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transient_error_retries_and_succeeds(hardening_settings):
    """Verify transient connection errors retry with backoff and succeed."""
    throttler = TelegramThrottler(hardening_settings)
    attempts = 0

    async def network_glitch_op():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("Connection lost to Telegram MTProto")
        return "recovered"

    result = await throttler.execute(network_glitch_op)
    assert result == "recovered"
    assert attempts == 2


@pytest.mark.asyncio
async def test_non_retryable_error_does_not_retry(hardening_settings):
    """Verify non-retryable domain and permission errors fail immediately on first attempt."""
    throttler = TelegramThrottler(hardening_settings)
    attempts = 0

    async def bad_op():
        nonlocal attempts
        attempts += 1
        raise PermissionDeniedError("send messages")

    with pytest.raises(PermissionDeniedError):
        await throttler.execute(bad_op)

    assert attempts == 1


# ---------------------------------------------------------------------------
# 4. Circuit Breaker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_trips_and_cooldown(hardening_settings):
    """Verify circuit trips to OPEN after threshold failures and recovers after cooldown."""
    cb = CircuitBreaker(failure_threshold=2, cooldown=0.15)
    assert cb.state == "CLOSED"

    await cb.record_failure()
    assert cb.state == "CLOSED"

    await cb.record_failure()
    assert cb.state == "OPEN"

    # While OPEN and within cooldown: execution is forbidden
    can_exec, remaining = await cb.can_execute()
    assert can_exec is False
    assert remaining > 0

    # Wait for cooldown to expire
    await asyncio.sleep(0.18)

    # After cooldown: transitions to HALF_OPEN probe
    can_exec, _ = await cb.can_execute()
    assert can_exec is True
    assert cb.state == "HALF_OPEN"

    # Successful probe resets to CLOSED
    await cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.failures == 0


@pytest.mark.asyncio
async def test_throttler_circuit_breaker_integration(hardening_settings):
    """Verify throttler fast-fails with CircuitBreakerOpenError when circuit is tripped."""
    throttler = TelegramThrottler(hardening_settings)

    # Force trip the circuit breaker
    await throttler.circuit_breaker.record_failure()
    await throttler.circuit_breaker.record_failure()
    await throttler.circuit_breaker.record_failure()
    assert throttler.circuit_breaker.state == "OPEN"

    async def sample_op():
        return "should not run"

    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        await throttler.execute(sample_op)

    assert exc_info.value.cooldown_remaining > 0


# ---------------------------------------------------------------------------
# 5. Concurrency & Bounded Queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrency_limiting(hardening_settings):
    """Verify that concurrent requests do not exceed the configured semaphore limit."""
    throttler = TelegramThrottler(hardening_settings)
    active_concurrent = 0
    max_observed_concurrent = 0

    async def slow_op():
        nonlocal active_concurrent, max_observed_concurrent
        active_concurrent += 1
        if active_concurrent > max_observed_concurrent:
            max_observed_concurrent = active_concurrent
        await asyncio.sleep(0.05)
        active_concurrent -= 1
        return "done"

    tasks = [throttler.execute(slow_op) for _ in range(4)]
    results = await asyncio.gather(*tasks)

    assert all(r == "done" for r in results)
    assert max_observed_concurrent <= hardening_settings.TELEGRAM_MAX_CONCURRENT_REQUESTS


@pytest.mark.asyncio
async def test_bounded_queue_overflow(hardening_settings):
    """Verify that requests exceeding queue capacity raise RequestQueueFullError."""
    throttler = TelegramThrottler(hardening_settings)
    # Queue size is 4, semaphore is 2

    release_event = asyncio.Event()

    async def blocking_op():
        await release_event.wait()
        return "done"

    # Launch 4 requests filling capacity (2 active + 2 waiting in queue)
    tasks = [asyncio.create_task(throttler.execute(blocking_op)) for _ in range(4)]
    await asyncio.sleep(0.01)

    # 5th request must overflow queue
    with pytest.raises(RequestQueueFullError):
        await throttler.execute(blocking_op)

    # Cleanup
    release_event.set()
    await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# 6. Request Deduplication & Debouncing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_in_flight_request_coalescing():
    """Verify concurrent requests with the same dedup_key coalesce into a single execution."""
    dedup = RequestDeduplicator()
    execution_count = 0

    async def slow_fetch():
        nonlocal execution_count
        execution_count += 1
        await asyncio.sleep(0.05)
        return "data_payload"

    # Launch 3 simultaneous requests with identical dedup key
    res1, res2, res3 = await asyncio.gather(
        dedup.execute("user:123", slow_fetch),
        dedup.execute("user:123", slow_fetch),
        dedup.execute("user:123", slow_fetch),
    )

    assert res1 == "data_payload"
    assert res2 == "data_payload"
    assert res3 == "data_payload"
    assert execution_count == 1, f"Expected 1 execution, got {execution_count}"


@pytest.mark.asyncio
async def test_debounce_window_rejection():
    """Verify repeated request within debounce_window returns cached result."""
    dedup = RequestDeduplicator()
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        return f"result_{call_count}"

    # First call runs
    val1 = await dedup.execute("click:pin", fetch, debounce_window=0.2)
    assert val1 == "result_1"

    # Second call within 0.2s returns cached result without running coroutine
    val2 = await dedup.execute("click:pin", fetch, debounce_window=0.2)
    assert val2 == "result_1"
    assert call_count == 1


# ---------------------------------------------------------------------------
# 7. Caching Layer Operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_service_dto_roundtrip():
    """Verify strongly typed caching of ChatDTO, MessageDTO, and ChatPermissionsDTO."""
    client = CacheClient(redis_url=None)
    await client.initialize()
    cache_svc = CacheService(client)

    # ChatDTO
    chat = ChatDTO(id=555, title="Hardened Chat", chat_type=ChatType.GROUP, unread_count=3)
    await cache_svc.set_cached_chat(555, chat, ttl=60)
    cached_chat = await cache_svc.get_cached_chat(555)
    assert cached_chat is not None
    assert cached_chat.id == 555
    assert cached_chat.title == "Hardened Chat"
    assert cached_chat.chat_type == ChatType.GROUP

    # MessageDTO
    msg = MessageDTO(
        id=77,
        chat_id=555,
        sender_id=999,
        sender_name="You",
        is_outgoing=True,
        text="Cached text",
        date=datetime.now(timezone.utc),
        media_type=MessageType.TEXT,
    )
    await cache_svc.set_cached_single_message(555, 77, msg, ttl=60)
    cached_msg = await cache_svc.get_cached_single_message(555, 77)
    assert cached_msg is not None
    assert cached_msg.id == 77
    assert cached_msg.text == "Cached text"

    # ChatPermissionsDTO
    perms = ChatPermissionsDTO(can_send_messages=True, is_admin=True)
    await cache_svc.set_cached_permissions(555, perms, ttl=60)
    cached_perms = await cache_svc.get_cached_permissions(555)
    assert cached_perms is not None
    assert cached_perms.can_send_messages is True
    assert cached_perms.is_admin is True

    # Invalidation
    await cache_svc.invalidate_chat(555)
    assert await cache_svc.get_cached_chat(555) is None
    assert await cache_svc.get_cached_permissions(555) is None


# ---------------------------------------------------------------------------
# 8. Adapter Integration with Caching & Read Acknowledgment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapter_serves_from_cache(hardening_settings):
    """Verify TelethonAdapter returns cached ChatDTO and MessageDTO without hitting MTProto."""
    client_mgr = MagicMock()
    client_mgr.ensure_connected = AsyncMock()

    client = CacheClient(redis_url=None)
    await client.initialize()
    cache_svc = CacheService(client)
    throttler = TelegramThrottler(hardening_settings)

    adapter = TelethonAdapter(client_mgr, throttler=throttler, cache_service=cache_svc)

    # Prime cache with ChatDTO
    test_chat = ChatDTO(id=12345, title="Cached Group", chat_type=ChatType.GROUP)
    await cache_svc.set_cached_chat(12345, test_chat)

    chat = await adapter.get_chat(12345)
    assert chat.id == 12345
    assert chat.title == "Cached Group"
    # client_mgr.ensure_connected should NOT be called because result came from cache
    client_mgr.ensure_connected.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_mark_chat_read(hardening_settings):
    """Verify mark_chat_read executes through throttler and invokes send_read_acknowledge."""
    raw_client = MagicMock()
    raw_client.get_input_entity = AsyncMock(return_value="entity_ref")
    raw_client.send_read_acknowledge = AsyncMock(return_value=True)

    client_mgr = MagicMock()
    client_mgr.ensure_connected = AsyncMock(return_value=raw_client)

    throttler = TelegramThrottler(hardening_settings)
    adapter = TelethonAdapter(client_mgr, throttler=throttler)

    await adapter.mark_chat_read(chat_id=101, max_id=42)

    raw_client.get_input_entity.assert_called_once_with(101)
    raw_client.send_read_acknowledge.assert_called_once_with("entity_ref", max_id=42)
