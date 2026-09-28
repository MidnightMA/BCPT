"""Main entrypoint orchestrating database, cache, Telethon, workers, and Telegram bot."""

import asyncio
import signal
import sys
from typing import Optional

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers.callbacks import handle_callback_query
from app.bot.handlers.errors import global_error_handler
from app.bot.handlers.media import handle_media_input
from app.bot.handlers.messages import handle_text_input
from app.bot.handlers.start import cancel_command, help_command, start_command
from app.cache.redis import close_cache, get_cache
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.database.session import close_db, init_db
from app.services.notification_service import NotificationService
from app.telegram.client import get_client_manager
from app.telegram.events import setup_telethon_events
from app.utils.cleanup import cleanup_stale_files
from app.workers.queue import get_task_queue
from app.workers.tasks import BackgroundScheduler

logger = get_logger("app.main")


class ApplicationRunner:
    """Manages full lifecycle of application components."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.bot_app: Optional[Application] = None
        self.scheduler: Optional[BackgroundScheduler] = None
        self.notification_service = NotificationService()
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Initialize all subsystems in sequential, deterministic order."""
        setup_logging(self.settings.LOG_LEVEL)
        logger.info("Starting Telegram Control Panel...")

        # 1. Directories
        self.settings.ensure_directories()

        # 2. Database
        await init_db()

        # 3. Cache
        await get_cache()

        # 4. Startup temp cleanup
        cleanup_stale_files(self.settings.TEMP_DIR, max_age_seconds=0)

        # 5. Background workers
        task_queue = get_task_queue()
        await task_queue.start()

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

        # 6. Telethon MTProto Client
        client_mgr = get_client_manager()
        try:
            await client_mgr.connect()
            setup_telethon_events(client_mgr, self.notification_service)
        except Exception as exc:
            logger.warning(
                f"Telethon connection warning: {exc}. "
                "Ensure setup_telethon.py has been run to generate the session."
            )

        # 7. Bale Bot Application (PTB configured with Bale Bot API endpoint)
        self.bot_app = (
            ApplicationBuilder()
            .token(self.settings.BOT_TOKEN)
            .base_url(self.settings.BALE_BASE_URL)
            .base_file_url(self.settings.BALE_FILE_URL)
            .build()
        )
        self.notification_service.set_bot(self.bot_app.bot)

        # Register Handlers
        self.bot_app.add_handler(CommandHandler("start", start_command))
        self.bot_app.add_handler(CommandHandler("help", help_command))
        self.bot_app.add_handler(CommandHandler("cancel", cancel_command))
        self.bot_app.add_handler(CallbackQueryHandler(handle_callback_query))
        self.bot_app.add_handler(
            MessageHandler(
                filters.ATTACHMENT
                | filters.PHOTO
                | filters.VIDEO
                | filters.AUDIO
                | filters.VOICE
                | filters.Document.ALL,
                handle_media_input,
            )
        )
        self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
        self.bot_app.add_error_handler(global_error_handler)

        logger.info(f"Initializing bot polling via Bale endpoint: {self.settings.BALE_BASE_URL}...")
        await self.bot_app.initialize()
        await self.bot_app.start()
        await self.bot_app.updater.start_polling()
        logger.info("Bale Control Panel is RUNNING. Press Ctrl+C to stop.")

    async def stop(self) -> None:
        """Gracefully terminate all services."""
        logger.info("Shutting down Telegram Control Panel...")

        # 1. Stop Bot Polling
        if self.bot_app:
            try:
                if self.bot_app.updater and self.bot_app.updater.running:
                    await self.bot_app.updater.stop()
                if self.bot_app.running:
                    await self.bot_app.stop()
                await self.bot_app.shutdown()
                logger.info("Bot polling stopped.")
            except Exception as exc:
                logger.warning(f"Error stopping bot application: {exc}")

        # 2. Stop Background Schedulers & Queue
        if self.scheduler:
            self.scheduler.stop()
        task_queue = get_task_queue()
        await task_queue.stop()

        # 3. Disconnect Telethon
        client_mgr = get_client_manager()
        await client_mgr.disconnect()

        # 4. Close Cache and Database
        await close_cache()
        await close_db()

        logger.info("Shutdown complete.")


def run() -> None:
    """Synchronous entrypoint setting up event loop and signal hooks."""
    runner = ApplicationRunner()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _signal_handler() -> None:
        logger.info("Received termination signal.")
        runner._shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, RuntimeError):
            # Windows or non-main thread fallback
            pass

    async def _main_coro() -> None:
        await runner.start()
        try:
            await runner._shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await runner.stop()

    try:
        loop.run_until_complete(_main_coro())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    run()
