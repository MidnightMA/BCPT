"""Markdown formatters for interactive prompts such as sending messages, files, and confirmation dialogs in Bale."""

from app.utils.telegram_utils import escape_markdown


def format_send_message_prompt(chat_title: str) -> str:
    """Prompt user to type a new text message."""
    title = escape_markdown(chat_title)
    return (
        f"✍️ *Send Text Message* to *{title}*\n\n"
        " _Type your message below and send it. It will be sent directly through your personal Telegram account.\n"
        "Or press 'Cancel' to return._ "
    )


def format_send_file_prompt(chat_title: str) -> str:
    """Prompt user to upload a file or document."""
    title = escape_markdown(chat_title)
    return (
        f"📎 *Send File/Media* to *{title}*\n\n"
        " _Send a document, photo, video, or audio file (with an optional caption).\n"
        "It will be uploaded directly through your personal Telegram account.\n"
        "Or press 'Cancel' to return._ "
    )


def format_delete_confirmation(chat_title: str, message_id: int) -> str:
    """Warning prompt before deleting a message."""
    title = escape_markdown(chat_title)
    return (
        f"⚠️ *Confirm Deletion*\n\n"
        f"Are you sure you want to delete message #{message_id} from *{title}* ?\n"
        " _This action will revoke the message for all participants where permissions permit._ "
    )
