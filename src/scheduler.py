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
from src.config import TIMEZONE, GMAIL_ADDRESS, GMAIL_APP_PASSWORD
from src.logging_utils import get_logger
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = get_logger(__name__)

# Configuration
BRIEF_HOUR = int(config("BRIEF_HOUR", default=8))
BRIEF_MINUTE = int(config("BRIEF_MINUTE", default=0))
USER_EMAIL = config("USER_EMAIL", default="")


def send_daily_brief():
    """Generate and send the daily brief via email."""
    logger.info("=== STARTING DAILY BRIEF JOB ===")

    if not USER_EMAIL:
        logger.error("USER_EMAIL not configured in .env")
        return

    if not GMAIL_ADDRESS:
        logger.error("GMAIL_ADDRESS not configured in .env")
        return

    try:
        # Get user's Google credentials from file
        logger.info(f"Loading credentials for {USER_EMAIL}")
        token_data = load_user_tokens(USER_EMAIL)

        if not token_data:
            logger.error(f"No credentials found for {USER_EMAIL}. User needs to authenticate first via the web app.")
            return

        # Convert to Credentials object (handles refresh automatically)
        credentials = get_credentials_from_tokens(token_data)

        if not credentials:
            logger.error("Failed to create credentials from tokens")
            return

        # Initialize assistant
        logger.info("Initializing assistant")
        assistant = AIAssistant(USER_EMAIL, credentials=credentials)

        # Generate daily brief
        logger.info("Generating daily brief")
        brief = assistant.generate_daily_brief()

        # Get current date for subject
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz)
        subject = f"📊 Daily Brief - {today.strftime('%A, %B %d, %Y')}"

        # Send email directly (not using @tool wrapper)
        logger.info(f"Sending daily brief email to {USER_EMAIL}")

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = GMAIL_ADDRESS
            msg['To'] = USER_EMAIL
            msg['Subject'] = subject
            msg.attach(MIMEText(brief, 'plain'))

            # Send via Gmail SMTP
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.send_message(msg)

            logger.info("=== DAILY BRIEF SENT SUCCESSFULLY ===")
            logger.info(f"Email sent to {USER_EMAIL}")

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            import traceback
            logger.error(traceback.format_exc())

    except Exception as e:
        logger.error(f"=== DAILY BRIEF FAILED ===")
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())


def run_scheduler():
    """Run the background scheduler."""
    logger.info("=== STARTING SCHEDULER ===")
    logger.info(f"Daily brief scheduled for {BRIEF_HOUR:02d}:{BRIEF_MINUTE:02d} {TIMEZONE}")
    logger.info(f"User: {USER_EMAIL}")

    if not USER_EMAIL:
        logger.error("USER_EMAIL not set in .env - scheduler cannot run")
        return

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
        name='Send Daily Brief Email',
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
