"""Lightweight asyncio-based background task queue."""

import asyncio
from typing import Any, Callable, Coroutine, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class AsyncTaskQueue:
    """Async background task manager to run non-blocking maintenance and operations."""

    def __init__(self, concurrency: int = 4) -> None:
        self.concurrency = concurrency
        self._queue: asyncio.Queue[tuple[str, Callable[[], Coroutine[Any, Any, Any]]]] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._running = False

    async def start(self) -> None:
        """Start worker pool."""
        if self._running:
            return
        self._running = True
        for i in range(self.concurrency):
            worker_task = asyncio.create_task(self._worker_loop(i), name=f"bg-worker-{i}")
            self._workers.append(worker_task)
        logger.info(f"Started {self.concurrency} background task workers.")

    async def stop(self) -> None:
        """Gracefully stop worker pool."""
        if not self._running:
            return
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Background task workers stopped.")

    async def enqueue(self, coro_func: Callable[[], Coroutine[Any, Any, Any]], name: str = "task") -> None:
        """Enqueue an async task to be executed by background workers."""
        await self._queue.put((name, coro_func))
        logger.debug(f"Enqueued background task: {name}")

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                name, task_func = await self._queue.get()
                logger.debug(f"Worker {worker_id} executing task '{name}'")
                try:
                    await task_func()
                    logger.debug(f"Worker {worker_id} completed task '{name}'")
                except Exception as exc:
                    logger.error(f"Error in background task '{name}': {exc}", exc_info=True)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Unexpected error in worker {worker_id}: {exc}", exc_info=True)


_task_queue: Optional[AsyncTaskQueue] = None


def get_task_queue() -> AsyncTaskQueue:
    """Return global singleton AsyncTaskQueue."""
    global _task_queue
    if _task_queue is None:
        _task_queue = AsyncTaskQueue(concurrency=3)
    return _task_queue
