"""Configuration management using pydantic-settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Bale Bot API Token (from @BotFather on Bale)
    BOT_TOKEN: str = Field(..., description="Bale Bot API Token")

    # Bale Bot API endpoints
    BALE_BASE_URL: str = Field(
        default="https://tapi.bale.ai/bot",
        description="Bale Bot API base URL",
    )
    BALE_FILE_URL: str = Field(
        default="https://tapi.bale.ai/file/bot",
        description="Bale Bot API file download base URL",
    )

    # Telethon MTProto credentials (from my.telegram.org)
    API_ID: int = Field(..., description="Telegram API ID")
    API_HASH: str = Field(..., description="Telegram API Hash")

    # Telethon session file path or name
    TELEGRAM_SESSION: str = Field(default="data/telegram.session", description="Telethon session storage path")

    # Authorized Bale Controller User IDs (whitelist)
    AUTHORIZED_USER_IDS: Union[List[int], str] = Field(
        default_factory=list,
        description="Comma-separated Bale user IDs authorized to use the control bot",
    )

    # Persistence
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///data/app.db",
        description="SQLAlchemy async database connection URL",
    )
    REDIS_URL: str | None = Field(default=None, description="Redis URL for caching and state management")

    # Directories
    TEMP_DIR: str = Field(default="tmp", description="Directory for temporary files")
    DATA_DIR: str = Field(default="data", description="Directory for persistent data")

    # Logging & Environment
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")

    # Default Pagination & UI
    DEFAULT_MESSAGES_PER_PAGE: int = Field(default=10, description="Messages per page in chat view")
    DEFAULT_CHATS_PER_PAGE: int = Field(default=6, description="Chats per page in dialogs list")
    CLEANUP_INTERVAL_MINUTES: int = Field(default=30, description="Interval for stale temp file cleanup")

    # Telegram Hardening & Rate Limiting
    TELEGRAM_RATE_LIMIT_GLOBAL: float = Field(
        default=5.0,
        description="Maximum Telegram MTProto operations per second globally",
    )
    TELEGRAM_PER_CHAT_RATE_LIMIT: float = Field(
        default=1.0,
        description="Minimum seconds between operations in the same chat",
    )
    TELEGRAM_MAX_CONCURRENT_REQUESTS: int = Field(
        default=3,
        description="Maximum concurrent MTProto requests",
    )
    TELEGRAM_MAX_CONCURRENT_MEDIA: int = Field(
        default=2,
        description="Maximum concurrent media upload/download operations",
    )
    TELEGRAM_REQUEST_QUEUE_MAX_SIZE: int = Field(
        default=50,
        description="Bounded queue limit for pending Telegram requests",
    )

    # FloodWait & Transient Error Retries
    TELEGRAM_AUTO_FLOOD_WAIT_MAX: int = Field(
        default=10,
        description="Maximum FloodWait seconds to automatically sleep and retry",
    )
    TELEGRAM_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retries for transient errors",
    )
    TELEGRAM_RETRY_BASE_DELAY: float = Field(
        default=1.0,
        description="Base delay for exponential backoff (seconds)",
    )
    TELEGRAM_RETRY_MAX_DELAY: float = Field(
        default=10.0,
        description="Maximum backoff delay (seconds)",
    )
    TELEGRAM_RETRY_JITTER: float = Field(
        default=0.5,
        description="Maximum random jitter added to backoff delay (seconds)",
    )

    # Circuit Breaker
    TELEGRAM_CIRCUIT_BREAKER_FAILURES: int = Field(
        default=5,
        description="Consecutive RPC/server failures before opening circuit breaker",
    )
    TELEGRAM_CIRCUIT_BREAKER_COOLDOWN: float = Field(
        default=30.0,
        description="Cooldown period in seconds when circuit breaker is open",
    )

    # Cache TTLs (seconds)
    TELEGRAM_CACHE_TTL_CHATS: int = Field(
        default=300,
        description="Cache TTL for chat metadata (seconds)",
    )
    TELEGRAM_CACHE_TTL_DIALOGS: int = Field(
        default=30,
        description="Cache TTL for dialogs list (seconds)",
    )
    TELEGRAM_CACHE_TTL_PERMISSIONS: int = Field(
        default=120,
        description="Cache TTL for permissions (seconds)",
    )
    TELEGRAM_CACHE_TTL_MESSAGES: int = Field(
        default=60,
        description="Cache TTL for message history and single messages (seconds)",
    )
    TELEGRAM_CACHE_TTL_PEERS: int = Field(
        default=600,
        description="Cache TTL for resolved peers/entities (seconds)",
    )

    # Request Deduplication & Read Acknowledgement
    TELEGRAM_DEDUPLICATION_WINDOW: float = Field(
        default=2.0,
        description="Window in seconds to deduplicate/debounce repeated identical requests",
    )
    TELEGRAM_AUTO_READ_ON_INSPECT: bool = Field(
        default=True,
        description="Acknowledge messages as read only when chat is explicitly opened in panel",
    )

    @field_validator("AUTHORIZED_USER_IDS", mode="before")
    @classmethod
    def parse_authorized_users(cls, v: Union[str, List[int], None]) -> List[int]:
        if not v:
            return []
        if isinstance(v, list):
            return [int(uid) for uid in v]
        if isinstance(v, str):
            clean = v.strip()
            if not clean:
                return []
            return [int(item.strip()) for item in clean.split(",") if item.strip()]
        return []

    def ensure_directories(self) -> None:
        """Create necessary data and temp directories if they do not exist."""
        Path(self.DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.TEMP_DIR).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings
