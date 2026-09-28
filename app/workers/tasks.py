"""Scheduled and recurring background maintenance tasks."""

import asyncio
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.cleanup import cleanup_stale_files

logger = get_logger(__name__)


async def run_periodic_cleanup(temp_dir: str, interval_seconds: int = 1800) -> None:
    """Periodically scan and purge stale files from the temp directory."""
    logger.info(f"Starting periodic temp file cleanup worker (interval: {interval_seconds}s)")
    while True:
        try:
            cleanup_stale_files(temp_dir, max_age_seconds=3600)
        except Exception as exc:
            logger.warning(f"Error in periodic cleanup task: {exc}")
        await asyncio.sleep(interval_seconds)


class BackgroundScheduler:
    """Manages recurring maintenance background coroutines."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        """Start recurring background maintenance loops."""
        cleanup_interval = self.settings.CLEANUP_INTERVAL_MINUTES * 60
        task = asyncio.create_task(
            run_periodic_cleanup(self.settings.TEMP_DIR, cleanup_interval),
            name="periodic-cleanup",
        )
        self._tasks.append(task)
        logger.info("Background recurring tasks scheduled.")

    def stop(self) -> None:
        """Cancel scheduled tasks."""
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        logger.info("Background recurring tasks stopped.")
