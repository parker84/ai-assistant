"""Telegram bot for mobile chat and on-demand daily briefs."""
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.config import TELEGRAM_BOT_TOKEN
from src.database import SessionLocal, TelegramUser, UserToken, init_db
from src.assistant import AIAssistant
from src.integrations.google_auth import load_user_tokens, get_credentials_from_tokens
from src.logging_utils import get_logger

logger = get_logger(__name__)


def get_user_email_for_chat(chat_id: int) -> str | None:
    """Look up user email for a Telegram chat ID. Returns None if not linked."""
    with SessionLocal() as session:
        row = session.query(TelegramUser).filter_by(telegram_chat_id=chat_id).first()
        return row.user_email if row else None


def link_telegram_user(chat_id: int, user_email: str) -> bool:
    """
    Link a Telegram chat to an app user. Returns True if the user exists in user_tokens.
    Creates or updates the telegram_users row.
    """
    with SessionLocal() as session:
        # Check that user has tokens (has signed in via web app)
        token_row = session.query(UserToken).filter_by(user_email=user_email).first()
        if not token_row:
            return False

        existing = session.query(TelegramUser).filter_by(telegram_chat_id=chat_id).first()
        if existing:
            existing.user_email = user_email
        else:
            session.add(
                TelegramUser(
                    telegram_chat_id=chat_id,
                    user_email=user_email,
                )
            )
        session.commit()
        return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start [email]. Links Telegram account to app user."""
    chat_id = update.effective_chat.id
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Link your account by sending:\n/start your@email.com\n\n"
            "You must have signed in at the web app first."
        )
        return

    email = context.args[0].strip().lower()
    if link_telegram_user(chat_id, email):
        await update.message.reply_text(
            f"✅ Linked to {email}. You can now chat here and use /brief for your daily brief."
        )
    else:
        await update.message.reply_text(
            f"No account found for {email}. Please sign in at the web app first, then try again."
        )


async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send daily brief on demand."""
    chat_id = update.effective_chat.id
    user_email = get_user_email_for_chat(chat_id)
    if not user_email:
        await update.message.reply_text(
            "Please link your account first: send /start your@email.com"
        )
        return

    token_data = load_user_tokens(user_email)
    if not token_data:
        await update.message.reply_text(
            "No credentials found for your account. Please sign in at the web app first."
        )
        return

    credentials = get_credentials_from_tokens(token_data)
    if not credentials:
        await update.message.reply_text("Failed to load credentials. Try signing in at the web app again.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    try:
        assistant = AIAssistant(user_email, credentials=credentials)
        brief = assistant.generate_daily_brief()
        if len(brief) > 4000:
            brief = brief[:3997] + "..."
        await update.message.reply_text(brief)
    except Exception as e:
        logger.exception("Failed to generate brief for Telegram")
        await update.message.reply_text(f"Sorry, I couldn't generate your brief: {e}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available commands."""
    await update.message.reply_text(
        "Commands:\n"
        "/start <email> — Link this chat to your app account (sign in at web app first)\n"
        "/brief — Get your daily brief now\n"
        "/help — Show this message\n\n"
        "Or just send a message to chat with your assistant (calendar, reminders, daily brief, etc.)."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message: run assistant chat and reply."""
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    if not text:
        return

    user_email = get_user_email_for_chat(chat_id)
    if not user_email:
        await update.message.reply_text(
            "Please link your account first: send /start your@email.com"
        )
        return

    token_data = load_user_tokens(user_email)
    if not token_data:
        await update.message.reply_text(
            "No credentials found for your account. Please sign in at the web app first."
        )
        return

    credentials = get_credentials_from_tokens(token_data)
    if not credentials:
        await update.message.reply_text("Failed to load credentials. Try signing in at the web app again.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        assistant = AIAssistant(user_email, credentials=credentials)
        # Run sync chat in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, assistant.chat, text)
        if len(response) > 4000:
            response = response[:3997] + "..."
        await update.message.reply_text(response)
    except Exception as e:
        logger.exception("Chat failed for Telegram user %s", user_email)
        await update.message.reply_text(f"Sorry, something went wrong: {e}")


def run_bot() -> None:
    """Run the Telegram bot (polling). Entry point for python -m src.telegram_bot."""
    init_db()

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Set it in .env to run the bot.")
        return

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("brief", cmd_brief))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Telegram bot starting (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
