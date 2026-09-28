"""Telegram and Bale text formatting, Markdown escaping, and truncation helpers."""

from datetime import datetime, timezone
from typing import Optional


def escape_markdown(text: Optional[str]) -> str:
    """
    Safely escape Markdown special characters for Bale.
    Prevents untrusted/external text from breaking Bale's Markdown format.
    """
    if not text:
        return ""
    text_str = str(text)
    # Escape backslash first, then markdown delimiters: *, _, [, ]
    for ch in ("\\", "*", "_", "[", "]"):
        text_str = text_str.replace(ch, f"\\{ch}")
    return text_str


def escape_html(text: Optional[str]) -> str:
    """Alias for escape_markdown to maintain backward compatibility."""
    return escape_markdown(text)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate long text to max_length adding suffix if shortened."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_bytes(size_bytes: Optional[int]) -> str:
    """Format byte counts into human-readable strings (e.g. 1.2 MB)."""
    if size_bytes is None or size_bytes < 0:
        return "Unknown size"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(size)} {units[unit_idx]}"
    return f"{size:.1f} {units[unit_idx]}"


def format_timestamp(dt: Optional[datetime]) -> str:
    """Format datetime into a clean human-readable string."""
    if not dt:
        return ""
    # Ensure datetime is represented nicely
    now = datetime.now(timezone.utc) if dt.tzinfo else datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%b %d, %H:%M")
