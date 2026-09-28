"""File cleanup safeguards and temporary file management."""

import os
import time
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def safe_remove_file(file_path: Optional[str | Path]) -> bool:
    """Safely delete a file if it exists without raising exceptions."""
    if not file_path:
        return False
    try:
        path = Path(file_path).resolve()
        if path.is_file():
            path.unlink()
            logger.debug(f"Removed temporary file: {path.name}")
            return True
    except Exception as exc:
        logger.warning(f"Failed to remove file {file_path}: {exc}")
    return False


def cleanup_stale_files(directory: str | Path, max_age_seconds: int = 3600) -> int:
    """
    Remove files in the given directory older than max_age_seconds.
    Returns the count of deleted files.
    """
    dir_path = Path(directory).resolve()
    if not dir_path.is_dir():
        return 0

    now = time.time()
    deleted_count = 0

    try:
        for entry in dir_path.iterdir():
            # Skip hidden files or gitkeep
            if entry.name.startswith("."):
                continue
            if entry.is_file():
                try:
                    file_age = now - entry.stat().st_mtime
                    if file_age > max_age_seconds:
                        entry.unlink()
                        deleted_count += 1
                except Exception as file_exc:
                    logger.debug(f"Could not delete stale file {entry}: {file_exc}")
    except Exception as exc:
        logger.warning(f"Error scanning directory {dir_path} during cleanup: {exc}")

    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} stale file(s) from {dir_path}")
    return deleted_count
