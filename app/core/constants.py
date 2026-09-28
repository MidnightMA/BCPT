"""Application constants, enums, and default limits."""

from enum import Enum, StrEnum


class ChatType(StrEnum):
    """Categorized chat types."""
    USER = "user"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"
    BOT = "bot"
    SAVED_MESSAGES = "saved_messages"


class MessageType(StrEnum):
    """Detected media / message types."""
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    STICKER = "sticker"
    SERVICE = "service"
    UNSUPPORTED = "unsupported"


class BotState(StrEnum):
    """Active interaction state for a user controller."""
    IDLE = "idle"
    WAITING_FOR_MESSAGE = "waiting_for_message"
    WAITING_FOR_REPLY = "waiting_for_reply"
    WAITING_FOR_EDIT = "waiting_for_edit"
    WAITING_FOR_FILE = "waiting_for_file"
    SEARCHING_CHATS = "searching_chats"
    SEARCHING_MESSAGES = "searching_messages"
    CONFIRMING_ACTION = "confirming_action"


class CallbackAction(StrEnum):
    """Callback query action tokens (kept short to stay within 64-byte Telegram limit)."""
    HOME = "home"
    CHATS = "chats"
    CHAT = "chat"
    MSGS = "msgs"
    FAVORITES = "favs"
    SETTINGS = "set"
    SEARCH_CHATS = "schats"
    SEARCH_MSGS = "smsgs"
    ACT_SEND = "asend"
    ACT_FILE = "afile"
    ACT_REPLY = "areply"
    ACT_EDIT = "aedit"
    ACT_DEL = "adel"
    ACT_PIN = "apin"
    ACT_FAV = "afav"
    ACT_INFO = "ainfo"
    CONFIRM_DEL = "cdel"
    TOGGLE_SETTING = "stog"
    CANCEL = "cancel"
    REFRESH = "ref"
    NOOP = "noop"


# Telegram limits
MAX_CALLBACK_LEN = 64
MAX_TELEGRAM_MSG_LEN = 4096
TELEGRAM_SAFE_MSG_LEN = 4000
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB (Bot API local limit)

# Default pagination counts
DEFAULT_MESSAGES_PER_PAGE = 10
DEFAULT_CHATS_PER_PAGE = 6
