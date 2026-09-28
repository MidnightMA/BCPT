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
