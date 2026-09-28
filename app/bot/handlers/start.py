"""Start, help, cancel command handlers and home dashboard renderer."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.formatters.chat import format_home_screen
from app.bot.keyboards.common import get_home_keyboard
from app.bot.states.conversation import get_state_manager
from app.core.logging import get_logger
from app.core.security import authorized_only
from app.services.account_service import AccountService
from app.telegram.adapter import get_telegram_adapter

logger = get_logger(__name__)


async def render_home_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render or edit the main home dashboard screen."""
    adapter = get_telegram_adapter()
    account_service = AccountService(adapter)
    summary = await account_service.get_account_summary()
    text = format_home_screen(summary)
    keyboard = get_home_keyboard()

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as exc:
            if "Message is not modified" not in str(exc):
                logger.debug(f"Failed to edit home view: {exc}")
    elif update.effective_message:
        await update.effective_message.reply_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    if user:
        state_mgr = await get_state_manager()
        await state_mgr.clear_state(user.id)
    await render_home_view(update, context)


@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "📖 *Bale Control Panel Help* \n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "This bot runs on Bale and acts as a control panel for your personal Telegram account.\n\n"
        " *Available Navigation:* \n"
        "• 💬 *Chats* : Browse, paginate, and search your Telegram dialogs.\n"
        "• ✍️ *Send Message* : Send texts directly from your account.\n"
        "• 📎 *Send File* : Upload documents, media, or photos.\n"
        "• ⭐ *Favorites* : Bookmark important chats for quick access.\n"
        "• ⚙️ *Settings* : Configure notifications and preferences.\n\n"
        "Commands:\n"
        "/start - Open home dashboard\n"
        "/help - Display this help manual\n"
        "/cancel - Abort active input prompt"
    )
    if update.effective_message:
        await update.effective_message.reply_text(help_text, parse_mode="Markdown")


@authorized_only
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command to abort active interactive input states."""
    user = update.effective_user
    if user:
        state_mgr = await get_state_manager()
        await state_mgr.clear_state(user.id)
    if update.effective_message:
        await update.effective_message.reply_text(
            "❌ Action cancelled. Returning to home dashboard.",
            parse_mode="Markdown",
        )
    await render_home_view(update, context)
