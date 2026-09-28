"""Tests for security guards, authorization, path traversal, and log scrubbing."""

import logging
from pathlib import Path

from app.core.logging import SecretScrubbingFilter
from app.core.security import generate_safe_temp_path, is_safe_path, is_user_authorized


def test_authorization_whitelist(mock_settings):
    """Verify that only explicitly whitelisted user IDs are authorized."""
    assert is_user_authorized(111222333) is True
    assert is_user_authorized(999888777) is True
    assert is_user_authorized(12345) is False
    assert is_user_authorized(0) is False


def test_path_traversal_detection(tmp_path):
    """Verify directory traversal attempts are properly detected and blocked."""
    base_dir = tmp_path / "sandbox"
    base_dir.mkdir()

    safe_target = base_dir / "safe_file.txt"
    unsafe_target = base_dir / ".." / "secret.txt"

    assert is_safe_path(base_dir, safe_target) is True
    assert is_safe_path(base_dir, unsafe_target) is False


def test_safe_temp_path_generation(tmp_path):
    """Verify that temp paths use sanitized extensions and unique UUID names."""
    temp_dir = tmp_path / "temp_files"

    # Malicious filenames attempting traversal
    path1 = generate_safe_temp_path("../../../etc/passwd", temp_dir)
    assert path1.parent == temp_dir.resolve()
    assert not path1.name.startswith("..")

    # Safe extension preservation
    path2 = generate_safe_temp_path("report.pdf", temp_dir)
    assert path2.suffix == ".pdf"
    assert path2.parent == temp_dir.resolve()

    # Special characters in filename
    path3 = generate_safe_temp_path("evil<>:\"/\\|?*.png", temp_dir)
    assert path3.suffix == ".png"


def test_secret_scrubbing_filter():
    """Verify secrets and sensitive tokens are masked in log messages."""
    filter_ = SecretScrubbingFilter()

    # Bot token scrubbing
    raw_log = "Starting bot with token 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567"
    record = logging.LogRecord("test", logging.INFO, "test.py", 10, raw_log, (), None)
    filter_.filter(record)
    assert "[REDACTED_BOT_TOKEN]" in record.msg
    assert "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567" not in record.msg

    # API hash scrubbing (32 hex characters)
    raw_hash = "Using API_HASH 0123456789abcdef0123456789abcdef for connection"
    record2 = logging.LogRecord("test", logging.INFO, "test.py", 11, raw_hash, (), None)
    filter_.filter(record2)
    assert "[REDACTED_API_HASH]" in record2.msg
    assert "0123456789abcdef0123456789abcdef" not in record2.msg
