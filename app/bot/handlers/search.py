"""Handlers for dialog and in-chat message search flows."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.formatters.chat import format_chat_list_header
from app.bot.formatters.message import format_message_entry
from app.bot.keyboards.chats import get_chat_list_keyboard
from app.bot.keyboards.common import build_cb, get_cancel_keyboard
from app.bot.states.conversation import get_state_manager
from app.core.constants import BotState, CallbackAction, DEFAULT_CHATS_PER_PAGE
from app.core.logging import get_logger
from app.services.search_service import SearchService
from app.telegram.adapter import get_telegram_adapter
from app.utils.telegram_utils import escape_html

logger = get_logger(__name__)


async def trigger_search_chats_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to type a query to search through dialogs."""
    user = update.effective_user
    if not user:
        return

    state_mgr = await get_state_manager()
    await state_mgr.set_state(user.id, BotState.SEARCHING_CHATS)

    prompt = (
        "🔎 *Search Dialogs* \n\n"
        " _Type a chat title, name, or username to search:\n"
        "Or press 'Cancel' to return._ "
    )
    keyboard = get_cancel_keyboard(CallbackAction.CHATS, 1)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def trigger_search_messages_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """Prompt user to type a query to search within a specific chat."""
    user = update.effective_user
    if not user:
        return

    state_mgr = await get_state_manager()
    await state_mgr.set_state(
        user.id,
        BotState.SEARCHING_MESSAGES,
        data={"chat_id": chat_id},
    )

    adapter = get_telegram_adapter()
    chat_dto = await adapter.get_chat(chat_id)

    prompt = (
        f"🔎 *Search Messages* in *{escape_html(chat_dto.title)}* \n\n"
        " _Type keywords to search within this chat's history:\n"
        "Or press 'Cancel' to return._ "
    )
    keyboard = get_cancel_keyboard(CallbackAction.CHAT, chat_id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=prompt,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def process_search_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: BotState,
    data: dict,
    query: str,
) -> None:
    """Execute search query based on active search state."""
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    adapter = get_telegram_adapter()
    search_service = SearchService(adapter)
    state_mgr = await get_state_manager()

    if state == BotState.SEARCHING_CHATS:
        paginated = await search_service.search_chats(
            query=query,
            page=1,
            per_page=DEFAULT_CHATS_PER_PAGE,
        )
        await state_mgr.clear_state(user.id)
        text = format_chat_list_header(paginated, query=query)
        keyboard = get_chat_list_keyboard(paginated)
        await msg.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif state == BotState.SEARCHING_MESSAGES:
        chat_id = data.get("chat_id")
        if not chat_id:
            await state_mgr.clear_state(user.id)
            return

        results = await search_service.search_messages_in_chat(
            chat_id=chat_id,
            query=query,
            limit=5,
        )
        await state_mgr.clear_state(user.id)

        chat_dto = await adapter.get_chat(chat_id)
        lines = [
            f"🔎 *Search in {escape_html(chat_dto.title)}* : _{escape_html(query)}_",
            f"Found {len(results)} message(s):",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        if not results:
            lines.append(" _No matching messages found._ ")
        else:
            for m in results:
                lines.append(format_message_entry(m))

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back to Chat", callback_data=build_cb(CallbackAction.CHAT, chat_id))]
        ])
        await msg.reply_text("\n\n".join(lines), parse_mode="Markdown", reply_markup=keyboard)
