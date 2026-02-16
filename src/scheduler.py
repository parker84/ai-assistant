"""Background scheduler for daily briefs and automated tasks."""
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from decouple import config

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from src.assistant import AIAssistant
from src.integrations.google_auth import load_user_tokens, get_credentials_from_tokens
from src.config import TIMEZONE, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, TELEGRAM_BOT_TOKEN
from src.database import SessionLocal, TelegramUser
from src.logging_utils import get_logger
import socket
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = get_logger(__name__)

# Configuration
BRIEF_HOUR = int(config("BRIEF_HOUR", default=8))
BRIEF_MINUTE = int(config("BRIEF_MINUTE", default=0))
USER_EMAIL = config("USER_EMAIL", default="")


def send_daily_brief():
    """Generate and send the daily brief via email and Telegram."""
    logger.info("=== STARTING DAILY BRIEF JOB ===")

    # --- Email delivery ---
    if USER_EMAIL and GMAIL_ADDRESS:
        try:
            logger.info(f"Loading credentials for {USER_EMAIL}")
            token_data = load_user_tokens(USER_EMAIL)

            if not token_data:
                logger.error(f"No credentials found for {USER_EMAIL}. User needs to authenticate first via the web app.")
            else:
                credentials = get_credentials_from_tokens(token_data)

                if not credentials:
                    logger.error("Failed to create credentials from tokens")
                else:
                    logger.info("Initializing assistant")
                    assistant = AIAssistant(USER_EMAIL, credentials=credentials)

                    logger.info("Generating daily brief")
                    brief = assistant.generate_daily_brief()

                    tz = pytz.timezone(TIMEZONE)
                    today = datetime.now(tz)
                    subject = f"📊 Daily Brief - {today.strftime('%A, %B %d, %Y')}"

                    logger.info(f"Sending daily brief email to {USER_EMAIL}")
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = GMAIL_ADDRESS
                        msg['To'] = USER_EMAIL
                        msg['Subject'] = subject
                        msg.attach(MIMEText(brief, 'plain'))

                        # Force IPv4 to avoid "Network is unreachable" on
                        # hosts where IPv6 DNS resolves but has no route.
                        addr = socket.getaddrinfo(
                            'smtp.gmail.com', 587,
                            socket.AF_INET, socket.SOCK_STREAM,
                        )[0][4]
                        with smtplib.SMTP(addr[0], addr[1], timeout=30) as server:
                            server.starttls()
                            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                            server.send_message(msg)

                        logger.info("=== EMAIL BRIEF SENT SUCCESSFULLY ===")
                    except Exception as e:
                        logger.error(f"Failed to send email: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"Email brief failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    else:
        logger.info("Email delivery skipped (USER_EMAIL or GMAIL_ADDRESS not configured)")

    # --- Telegram delivery ---
    send_brief_via_telegram()


def send_brief_via_telegram():
    """Send daily brief to all linked Telegram users."""
    if not TELEGRAM_BOT_TOKEN:
        logger.info("TELEGRAM_BOT_TOKEN not set, skipping Telegram delivery")
        return

    with SessionLocal() as session:
        telegram_users = session.query(TelegramUser).all()

    if not telegram_users:
        logger.info("No Telegram users linked, skipping Telegram delivery")
        return

    import telegram
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

    for tg_user in telegram_users:
        try:
            logger.info(f"Generating Telegram brief for {tg_user.user_email}")
            token_data = load_user_tokens(tg_user.user_email)
            if not token_data:
                logger.warning(f"No credentials for {tg_user.user_email}, skipping")
                continue

            credentials = get_credentials_from_tokens(token_data)
            if not credentials:
                logger.warning(f"Failed to create credentials for {tg_user.user_email}, skipping")
                continue

            assistant = AIAssistant(tg_user.user_email, credentials=credentials)
            brief = assistant.generate_daily_brief()

            import asyncio
            asyncio.run(bot.send_message(chat_id=tg_user.telegram_chat_id, text=brief))
            logger.info(f"Telegram brief sent to chat {tg_user.telegram_chat_id}")

        except Exception as e:
            logger.error(f"Failed to send Telegram brief to {tg_user.user_email}: {e}")
            import traceback
            logger.error(traceback.format_exc())


def run_scheduler():
    """Run the background scheduler."""
    logger.info("=== STARTING SCHEDULER ===")
    logger.info(f"Daily brief scheduled for {BRIEF_HOUR:02d}:{BRIEF_MINUTE:02d} {TIMEZONE}")
    logger.info(f"User: {USER_EMAIL or '(none, Telegram-only)'}")

    scheduler = BlockingScheduler(timezone=TIMEZONE)

    # Schedule daily brief
    scheduler.add_job(
        send_daily_brief,
        trigger=CronTrigger(
            hour=BRIEF_HOUR,
            minute=BRIEF_MINUTE,
            timezone=TIMEZONE
        ),
        id='daily_brief',
        name='Send Daily Brief',
        replace_existing=True
    )

    logger.info("Scheduler started. Press Ctrl+C to exit.")

    # Log next run time
    jobs = scheduler.get_jobs()
    if jobs:
        job = jobs[0]
        try:
            next_run = job.trigger.get_next_fire_time(None, datetime.now(pytz.timezone(TIMEZONE)))
            current_time = datetime.now(pytz.timezone(TIMEZONE))
            logger.info(f"Current time: {current_time}")
            logger.info(f"Next run: {next_run}")
        except Exception as e:
            logger.warning(f"Could not determine next run time: {e}")
            logger.info(f"Job scheduled: {job.name}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        scheduler.shutdown()


if __name__ == "__main__":
    # send_daily_brief()
    run_scheduler()
