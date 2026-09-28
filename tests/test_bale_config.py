"""Tests to verify Bale Bot API configuration and Telethon settings isolation."""

from telegram.ext import ApplicationBuilder

from app.core.config import Settings


def test_bale_settings_defaults(tmp_path):
    """Verify Bale endpoints and Telethon isolation in Settings."""
    temp_dir = tmp_path / "tmp"
    data_dir = tmp_path / "data"
    temp_dir.mkdir()
    data_dir.mkdir()

    settings = Settings(
        BOT_TOKEN="bale_bot_token_12345",
        API_ID=987654,
        API_HASH="fedcba9876543210fedcba9876543210",
        TELEGRAM_SESSION=str(data_dir / "telegram.session"),
        AUTHORIZED_USER_IDS=[12345],
        TEMP_DIR=str(temp_dir),
        DATA_DIR=str(data_dir),
    )

    # 1. Bale Bot API endpoints are correctly configured
    assert settings.BALE_BASE_URL == "https://tapi.bale.ai/bot"
    assert settings.BALE_FILE_URL == "https://tapi.bale.ai/file/bot"
    assert settings.BOT_TOKEN == "bale_bot_token_12345"

    # 2. Telegram MTProto settings remain intact
    assert settings.API_ID == 987654
    assert settings.API_HASH == "fedcba9876543210fedcba9876543210"
    assert settings.TELEGRAM_SESSION == str(data_dir / "telegram.session")


def test_ptb_application_builder_with_bale(mock_settings):
    """Verify python-telegram-bot ApplicationBuilder attaches Bale base_url."""
    app = (
        ApplicationBuilder()
        .token(mock_settings.BOT_TOKEN)
        .base_url(mock_settings.BALE_BASE_URL)
        .base_file_url(mock_settings.BALE_FILE_URL)
        .build()
    )

    # In python-telegram-bot, bot.base_url is formed using the custom base_url
    assert "tapi.bale.ai" in app.bot.base_url
    assert mock_settings.BOT_TOKEN in app.bot.base_url
    assert "api.telegram.org" not in app.bot.base_url
