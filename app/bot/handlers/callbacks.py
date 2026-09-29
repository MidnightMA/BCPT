"""Central callback query router dispatching inline button interactions."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.chats import (
    handle_join_channel,
    handle_toggle_favorite,
    render_chat_info_view,
    render_chats_view,
    trigger_open_peer_prompt,
)
from app.bot.handlers.media import trigger_send_file_prompt
from app.bot.handlers.messages import (
    handle_confirm_delete,
    handle_pin_message,
    render_chat_screen,
    render_message_detail_view,
    trigger_delete_confirmation,
    trigger_edit_message_prompt,
    trigger_prompt_view_message,
    trigger_send_message_prompt,
)
from app.bot.handlers.search import trigger_search_chats_prompt, trigger_search_messages_prompt
from app.bot.handlers.settings import handle_toggle_setting, render_settings_view
from app.bot.handlers.start import render_home_view
from app.bot.keyboards.common import parse_cb
from app.bot.states.conversation import get_state_manager
from app.core.constants import CallbackAction
from app.core.logging import get_logger
from app.core.security import authorized_only
from app.utils.telegram_utils import escape_markdown

logger = get_logger(__name__)


ACTIONS_WITH_CUSTOM_ANSWER = {
    CallbackAction.CONFIRM_DEL,
    CallbackAction.ACT_PIN,
    CallbackAction.ACT_FAV,
    CallbackAction.JOIN_CHAN,
    CallbackAction.TOGGLE_SETTING,
}


@authorized_only
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route callback queries to appropriate feature handlers based on action token."""
    query = update.callback_query
    if not query or not query.data:
        return

    action, args = parse_cb(query.data)
    logger.debug(f"Routing callback action: '{action}' with args: {args}")

    # Acknowledge callback immediately to eliminate loading spinner for standard views
    if action not in ACTIONS_WITH_CUSTOM_ANSWER:
        try:
            await query.answer()
        except Exception as exc:
            logger.debug(f"Failed to answer callback query: {exc}")

    try:
        # Home
        if action == CallbackAction.HOME:
            user = update.effective_user
            if user:
                state_mgr = await get_state_manager()
                await state_mgr.clear_state(user.id)
            await render_home_view(update, context)

        # Dialogs / Chats list
        elif action == CallbackAction.CHATS:
            page = int(args[0]) if args else 1
            await render_chats_view(update, context, page=page, favorites_only=False)

        # Favorites list
        elif action == CallbackAction.FAVORITES:
            page = int(args[0]) if args else 1
            await render_chats_view(update, context, page=page, favorites_only=True)

        # Open specific chat view
        elif action == CallbackAction.CHAT:
            chat_id = int(args[0])
            user = update.effective_user
            if user:
                state_mgr = await get_state_manager()
                await state_mgr.clear_state(user.id)
            await render_chat_screen(update, context, chat_id=chat_id)

        # Open peer prompt (username, link, or ID)
        elif action == CallbackAction.OPEN_PEER:
            await trigger_open_peer_prompt(update, context)

        # Join public channel
        elif action == CallbackAction.JOIN_CHAN:
            channel_id = int(args[0])
            await handle_join_channel(update, context, channel_id=channel_id)

        # View complete message with all media
        elif action == CallbackAction.VIEW_MSG:
            chat_id = int(args[0])
            msg_id = int(args[1])
            await render_message_detail_view(update, context, chat_id=chat_id, message_id=msg_id)

        # Prompt for message ID to view
        elif action == CallbackAction.PROMPT_VIEW_MSG:
            chat_id = int(args[0])
            await trigger_prompt_view_message(update, context, chat_id=chat_id)

        # Paginate message history in chat
        elif action == CallbackAction.MSGS:
            chat_id = int(args[0])
            offset_id = int(args[1]) if len(args) > 1 else 0
            await render_chat_screen(update, context, chat_id=chat_id, offset_id=offset_id)

        # Send message prompt
        elif action == CallbackAction.ACT_SEND:
            chat_id = int(args[0])
            await trigger_send_message_prompt(update, context, chat_id=chat_id)

        # Send file prompt
        elif action == CallbackAction.ACT_FILE:
            chat_id = int(args[0])
            await trigger_send_file_prompt(update, context, chat_id=chat_id)

        # Reply prompt
        elif action == CallbackAction.ACT_REPLY:
            chat_id = int(args[0])
            msg_id = int(args[1]) if len(args) > 1 else None
            await trigger_send_message_prompt(update, context, chat_id=chat_id, reply_to_msg_id=msg_id)

        # Edit message prompt
        elif action == CallbackAction.ACT_EDIT:
            chat_id = int(args[0])
            msg_id = int(args[1])
            await trigger_edit_message_prompt(update, context, chat_id=chat_id, message_id=msg_id)

        # Delete message confirmation
        elif action == CallbackAction.ACT_DEL:
            chat_id = int(args[0])
            msg_id = int(args[1])
            await trigger_delete_confirmation(update, context, chat_id=chat_id, message_id=msg_id)

        # Confirm delete action
        elif action == CallbackAction.CONFIRM_DEL:
            chat_id = int(args[0])
            msg_id = int(args[1])
            await handle_confirm_delete(update, context, chat_id=chat_id, message_id=msg_id)

        # Pin message
        elif action == CallbackAction.ACT_PIN:
            chat_id = int(args[0])
            msg_id = int(args[1])
            await handle_pin_message(update, context, chat_id=chat_id, message_id=msg_id)

        # Favorite toggle
        elif action == CallbackAction.ACT_FAV:
            chat_id = int(args[0])
            await handle_toggle_favorite(update, context, chat_id=chat_id)

        # Chat info
        elif action == CallbackAction.ACT_INFO:
            chat_id = int(args[0])
            await render_chat_info_view(update, context, chat_id=chat_id)

        # Search dialogs
        elif action == CallbackAction.SEARCH_CHATS:
            await trigger_search_chats_prompt(update, context)

        # Search messages in chat
        elif action == CallbackAction.SEARCH_MSGS:
            chat_id = int(args[0])
            await trigger_search_messages_prompt(update, context, chat_id=chat_id)

        # Settings menu
        elif action == CallbackAction.SETTINGS:
            await render_settings_view(update, context)

        # Toggle setting
        elif action == CallbackAction.TOGGLE_SETTING:
            setting_key = args[0]
            await handle_toggle_setting(update, context, setting_key)

        # Cancel interactive input
        elif action == CallbackAction.CANCEL:
            user = update.effective_user
            if user:
                state_mgr = await get_state_manager()
                await state_mgr.clear_state(user.id)
            if args:
                target_chat_id = int(args[0])
                await render_chat_screen(update, context, chat_id=target_chat_id)
            else:
                await render_home_view(update, context)

        # No-op placeholder buttons (e.g. page count indicator)
        elif action == CallbackAction.NOOP:
            pass

        else:
            logger.warning(f"Unhandled callback action: '{action}'")

    except Exception as exc:
        logger.error(f"Error executing callback action '{action}': {exc}", exc_info=True)
        error_msg = f"⚠️ *Error:* {escape_markdown(str(exc))}"
        try:
            await query.edit_message_text(error_msg, parse_mode="Markdown")
        except Exception:
            pass
