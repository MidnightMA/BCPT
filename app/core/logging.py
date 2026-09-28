"""Structured logging configuration with secret and credential scrubbing."""

import logging
import re
import sys
from typing import Any


class SecretScrubbingFilter(logging.Filter):
    """Filter that masks sensitive tokens, hashes, and session strings in log messages."""

    PATTERNS = [
        # Bot token format: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
        (re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b"), "[REDACTED_BOT_TOKEN]"),
        # API hash: 32 hex chars
        (re.compile(r"\b[0-9a-fA-F]{32}\b"), "[REDACTED_API_HASH]"),
        # Phone numbers: +1234567890
        (re.compile(r"\+\d{7,15}"), "[REDACTED_PHONE]"),
        # Telethon StringSession (1BVts...)
        (re.compile(r"\b1[A-Za-z0-9+/=]{100,}\b"), "[REDACTED_SESSION]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.scrub_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.scrub_any(v) for k, v in record.args.items()}
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(self.scrub_any(arg) for arg in record.args)
        return True

    @classmethod
    def scrub_text(cls, text: str) -> str:
        for pattern, replacement in cls.PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    @classmethod
    def scrub_any(cls, value: Any) -> Any:
        if isinstance(value, str):
            return cls.scrub_text(value)
        return value


def setup_logging(log_level: str = "INFO") -> None:
    """Initialize application-wide logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    scrubber = SecretScrubbingFilter()

    # Configure stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(scrubber)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)

    # Quiet overly chatty third-party loggers
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for the specified module name."""
    return logging.getLogger(name)
