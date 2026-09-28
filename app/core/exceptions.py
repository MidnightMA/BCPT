"""Domain exception hierarchy for the Telegram Control Panel."""


class AppException(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str = "An application error occurred.", user_message: str | None = None):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or message


class AuthError(AppException):
    """Raised when an authorization or authentication check fails."""
    def __init__(self, message: str = "Access denied. You are not authorized to use this bot."):
        super().__init__(message=message, user_message="⛔ *Access Denied* : You are not authorized.")


class TelegramClientError(AppException):
    """Base error for Telethon MTProto client operations."""


class FloodWaitError(TelegramClientError):
    """Raised when Telegram imposes an MTProto FloodWait rate limit."""
    def __init__(self, seconds: int, message: str | None = None):
        self.seconds = max(1, int(seconds))
        default_msg = f"Telegram rate limit: FloodWait required for {self.seconds} seconds."
        user_msg = f"⏳ *Rate Limit Reached* : Telegram requires waiting *{self.seconds}s* before retrying."
        super().__init__(message=message or default_msg, user_message=user_msg)


class ChatNotFoundError(TelegramClientError):
    """Raised when a specified Telegram chat cannot be found or accessed."""
    def __init__(self, chat_id: int | str, message: str | None = None):
        self.chat_id = chat_id
        default_msg = f"Chat '{chat_id}' was not found or is inaccessible."
        user_msg = f"⚠️ *Chat Not Found* : Unable to access chat {chat_id}."
        super().__init__(message=message or default_msg, user_message=user_msg)


class MessageNotFoundError(TelegramClientError):
    """Raised when a specific message ID does not exist."""
    def __init__(self, message_id: int, message: str | None = None):
        self.message_id = message_id
        default_msg = f"Message with ID '{message_id}' not found."
        user_msg = f"⚠️ *Message Not Found* : The message (ID: {message_id}) no longer exists."
        super().__init__(message=message or default_msg, user_message=user_msg)


class PermissionDeniedError(TelegramClientError):
    """Raised when the Telegram user account lacks required chat permissions."""
    def __init__(self, action: str = "perform this action", message: str | None = None):
        self.action = action
        default_msg = f"Permission denied to {action} in this chat."
        user_msg = f"🚫 *Permission Denied* : Your Telegram account cannot {action} in this chat."
        super().__init__(message=message or default_msg, user_message=user_msg)


class MediaProcessingError(TelegramClientError):
    """Raised when media download or upload fails."""
    def __init__(self, message: str = "Media operation failed.", user_message: str | None = None):
        super().__init__(message=message, user_message=user_message or "⚠️ *Media Error* : Failed to process file.")


class ConnectionFailedError(TelegramClientError):
    """Raised when Telethon fails to connect to Telegram MTProto servers."""
    def __init__(self, message: str = "Telethon connection failed."):
        super().__init__(message=message, user_message="⚠️ *Connection Error* : Unable to connect to Telegram.")


class ServiceError(AppException):
    """Raised when a service-layer operation fails."""


class StorageError(AppException):
    """Raised when database or cache persistence fails."""


class StateError(AppException):
    """Raised when an invalid state transition or expired interaction occurs."""
