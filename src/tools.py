"""Calendar tools for Agno agent."""
from agno.tools import tool
from datetime import datetime, timedelta
from typing import List
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.config import TIMEZONE, GMAIL_ADDRESS, GMAIL_APP_PASSWORD
from src.logging_utils import get_logger

logger = get_logger(__name__)

# Module-level credentials storage - set this before using tools
_credentials = None
_knowledge_base = None


def set_credentials(credentials):
    """Set the Google credentials for calendar tools."""
    global _credentials
    _credentials = credentials
    logger.info("Calendar credentials set")


def get_credentials():
    """Get the current Google credentials."""
    global _credentials
    if _credentials is None:
        logger.error("Calendar credentials not set!")
    return _credentials


def set_knowledge_base(kb):
    """Set the KnowledgeBase instance for reminder tools."""
    global _knowledge_base
    _knowledge_base = kb
    logger.info("Knowledge base set for tools")


def _get_knowledge_base():
    """Get the current KnowledgeBase instance."""
    global _knowledge_base
    if _knowledge_base is None:
        raise Exception("Knowledge base not set. Please authenticate first.")
    return _knowledge_base


def _get_calendar_service():
    """Build Google Calendar service."""
    from googleapiclient.discovery import build
    credentials = get_credentials()
    if not credentials:
        raise Exception("Google credentials not set. Please authenticate first.")
    return build("calendar", "v3", credentials=credentials)


# =========================
# Calendar Query Tools
# =========================

@tool
def get_todays_events() -> str:
    """
    Get all calendar events for today.
    
    WHEN TO USE:
    - User asks "what's on my calendar today?"
    - User wants to know their schedule for today
    - You need to check today's events before scheduling something
    
    RETURNS:
    - A formatted string listing all today's events with times
    """
    logger.info("=== GET TODAY'S EVENTS ===")
    try:
        service = _get_calendar_service()
        tz = pytz.timezone(TIMEZONE)
        
        now = datetime.now(tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = events_result.get("items", [])
        logger.info(f"Found {len(events)} events today")
        
        if not events:
            return "No events scheduled for today."
        
        lines = ["📅 Today's Events:"]
        for event in events:
            start = event.get("start", {})
            if "dateTime" in start:
                event_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                time_str = event_time.strftime("%I:%M %p")
            else:
                time_str = "All day"
            
            summary = event.get("summary", "No title")
            location = event.get("location", "")
            location_str = f" @ {location}" if location else ""
            lines.append(f"• {time_str}: {summary}{location_str}")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Failed to get today's events: {e}")
        return f"Error getting today's events: {str(e)}"


@tool
def get_upcoming_events(days: int = 7) -> str:
    """
    Get upcoming calendar events for the next N days.
    
    WHEN TO USE:
    - User asks about their upcoming schedule
    - User wants to see their week ahead
    - You need to analyze the user's calendar
    
    ARGS:
    - days (int): Number of days to look ahead (default: 7)
    
    RETURNS:
    - A formatted string listing upcoming events grouped by day
    """
    logger.info(f"=== GET UPCOMING EVENTS ({days} days) ===")
    try:
        service = _get_calendar_service()
        tz = pytz.timezone(TIMEZONE)
        
        now = datetime.now(tz)
        end_date = now + timedelta(days=days)
        
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = events_result.get("items", [])
        logger.info(f"Found {len(events)} upcoming events")
        
        if not events:
            return f"No events scheduled for the next {days} days."
        
        lines = [f"📅 Upcoming Events ({days} days):"]
        current_date = None
        
        for event in events:
            start = event.get("start", {})
            if "dateTime" in start:
                event_datetime = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                time_str = event_datetime.strftime("%I:%M %p")
            else:
                event_datetime = datetime.fromisoformat(start.get("date", ""))
                time_str = "All day"
            
            date_str = event_datetime.strftime("%A, %B %d")
            if date_str != current_date:
                current_date = date_str
                lines.append(f"\n**{date_str}**")
            
            summary = event.get("summary", "No title")
            location = event.get("location", "")
            location_str = f" @ {location}" if location else ""
            lines.append(f"• {time_str}: {summary}{location_str}")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Failed to get upcoming events: {e}")
        return f"Error getting upcoming events: {str(e)}"


@tool
def find_free_time_slots(
    date: str,
    duration_minutes: int = 60,
    start_hour: int = 9,
    end_hour: int = 17
) -> str:
    """
    Find available time slots on a specific day.
    
    WHEN TO USE:
    - User wants to schedule a meeting and needs to find available time
    - User asks "when am I free on Tuesday?"
    - You need to suggest times for a new event
    
    ARGS:
    - date (str): The date to check in YYYY-MM-DD format
    - duration_minutes (int): Length of the time slot needed (default: 60)
    - start_hour (int): Start of working hours (default: 9)
    - end_hour (int): End of working hours (default: 17)
    
    RETURNS:
    - A list of available time slots
    """
    logger.info(f"=== FIND FREE SLOTS on {date} ===")
    try:
        service = _get_calendar_service()
        tz = pytz.timezone(TIMEZONE)
        
        target_date = datetime.strptime(date, "%Y-%m-%d")
        target_date = tz.localize(target_date)
        
        start_of_day = target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = events_result.get("items", [])
        
        free_slots = []
        current_time = start_of_day
        
        for event in events:
            event_start_str = event.get("start", {}).get("dateTime")
            event_end_str = event.get("end", {}).get("dateTime")
            
            if not event_start_str or not event_end_str:
                continue
            
            event_start = datetime.fromisoformat(event_start_str.replace("Z", "+00:00")).astimezone(tz)
            event_end = datetime.fromisoformat(event_end_str.replace("Z", "+00:00")).astimezone(tz)
            
            if current_time + timedelta(minutes=duration_minutes) <= event_start:
                free_slots.append({
                    "start": current_time.strftime("%I:%M %p"),
                    "end": event_start.strftime("%I:%M %p"),
                })
            
            if event_end > current_time:
                current_time = event_end
        
        if current_time + timedelta(minutes=duration_minutes) <= end_of_day:
            free_slots.append({
                "start": current_time.strftime("%I:%M %p"),
                "end": end_of_day.strftime("%I:%M %p"),
            })
        
        if not free_slots:
            return f"No available slots of {duration_minutes} minutes on {date}"
        
        lines = [f"🕐 Available time slots on {target_date.strftime('%A, %B %d')}:"]
        for slot in free_slots:
            lines.append(f"• {slot['start']} - {slot['end']}")
        
        logger.info(f"Found {len(free_slots)} free slots")
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Failed to find free slots: {e}")
        return f"Error finding free slots: {str(e)}"


# =========================
# Calendar Creation Tools
# =========================

@tool
def create_calendar_event(
    title: str,
    date: str,
    start_time: str,
    duration_minutes: int = 60,
    description: str = "",
    location: str = "",
    attendees: List[str] = None
) -> str:
    """
    Create a new calendar event.
    
    WHEN TO USE:
    - User wants to add an event to their calendar
    - User says "schedule a meeting" or "add to my calendar"
    - After confirming event details with the user
    
    ARGS:
    - title (str): The event title/summary
    - date (str): The date in YYYY-MM-DD format
    - start_time (str): The start time in HH:MM format (24-hour)
    - duration_minutes (int): How long the event is (default: 60)
    - description (str): Optional event description
    - location (str): Optional event location
    - attendees (List[str]): Optional list of email addresses to invite
    
    RETURNS:
    - Confirmation message with event details and link
    """
    logger.info(f"=== CREATE EVENT: {title} ===")
    logger.info(f"Date: {date}, Time: {start_time}, Duration: {duration_minutes}min")
    
    try:
        service = _get_calendar_service()
        tz = pytz.timezone(TIMEZONE)
        
        # Parse date and time
        event_date = datetime.strptime(date, "%Y-%m-%d")
        hour, minute = map(int, start_time.split(":"))
        start_datetime = tz.localize(event_date.replace(hour=hour, minute=minute))
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        event = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
        }
        
        if location:
            event["location"] = location
        
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        
        logger.info(f"Event payload: {event}")
        
        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all" if attendees else "none",
        ).execute()
        
        logger.info(f"=== EVENT CREATED SUCCESSFULLY ===")
        logger.info(f"Event ID: {created_event.get('id')}")
        logger.info(f"Event link: {created_event.get('htmlLink')}")
        
        return f"""✅ Event created successfully!

**{title}**
📅 {start_datetime.strftime('%A, %B %d, %Y')}
🕐 {start_datetime.strftime('%I:%M %p')} - {end_datetime.strftime('%I:%M %p')}
{f'📍 {location}' if location else ''}
{f'👥 Invited: {", ".join(attendees)}' if attendees else ''}

[View in Google Calendar]({created_event.get('htmlLink')})"""
        
    except Exception as e:
        logger.error(f"=== EVENT CREATION FAILED ===")
        logger.error(f"Error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"❌ Failed to create event: {str(e)}"


@tool
def create_birthday_reminder(
    name: str,
    date: str
) -> str:
    """
    Create a recurring yearly birthday event.
    
    WHEN TO USE:
    - User wants to add someone's birthday to their calendar
    - User says "remember [name]'s birthday on [date]"
    - User wants a yearly recurring birthday reminder
    
    ARGS:
    - name (str): The person's name
    - date (str): The birthday date in YYYY-MM-DD format (year can be any year)
    
    RETURNS:
    - Confirmation message with the birthday event details
    """
    logger.info(f"=== CREATE BIRTHDAY: {name} on {date} ===")
    
    try:
        service = _get_calendar_service()
        
        birthday_date = datetime.strptime(date, "%Y-%m-%d")
        start_date_str = birthday_date.strftime("%Y-%m-%d")
        end_date = birthday_date + timedelta(days=1)
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        event = {
            "summary": f"🎂 {name}'s Birthday",
            "description": f"Don't forget to wish {name} a happy birthday!",
            "start": {"date": start_date_str},
            "end": {"date": end_date_str},
            "recurrence": ["RRULE:FREQ=YEARLY"],
        }
        
        logger.info(f"Birthday event payload: {event}")
        
        created_event = service.events().insert(
            calendarId="primary",
            body=event,
        ).execute()
        
        logger.info(f"=== BIRTHDAY CREATED SUCCESSFULLY ===")
        logger.info(f"Event ID: {created_event.get('id')}")
        
        return f"""✅ Birthday reminder created!

🎂 **{name}'s Birthday**
📅 {birthday_date.strftime('%B %d')} (recurring yearly)

[View in Google Calendar]({created_event.get('htmlLink')})"""
        
    except Exception as e:
        logger.error(f"=== BIRTHDAY CREATION FAILED ===")
        logger.error(f"Error: {e}")
        return f"❌ Failed to create birthday reminder: {str(e)}"


def create_recurring_all_day_event(title: str, date_str: str) -> str:
    """
    Create a recurring yearly all-day event. Used for crucial events (birthdays, anniversaries, etc).
    All-day events don't block meeting slots.
    """
    logger.info(f"=== CREATE RECURRING ALL-DAY: {title} on {date_str} ===")
    try:
        from src.knowledge_base import resolve_crucial_event_date
        from datetime import datetime as dt

        resolved = resolve_crucial_event_date(date_str)
        if not resolved:
            return f"❌ Could not parse date: {date_str}"

        service = _get_calendar_service()
        event_date = dt.strptime(resolved, "%Y-%m-%d")
        start_date_str = event_date.strftime("%Y-%m-%d")
        end_date = event_date + timedelta(days=1)
        end_date_str = end_date.strftime("%Y-%m-%d")

        event = {
            "summary": title,
            "description": f"Recurring reminder",
            "start": {"date": start_date_str},
            "end": {"date": end_date_str},
            "recurrence": ["RRULE:FREQ=YEARLY"],
        }

        created_event = service.events().insert(calendarId="primary", body=event).execute()
        logger.info(f"Created: {created_event.get('id')}")
        return f"✅ Added to calendar: {title}"
    except Exception as e:
        logger.error(f"Failed: {e}")
        return f"❌ Failed: {str(e)}"


@tool
def schedule_interview(
    candidate_name: str,
    interviewer_emails: List[str],
    date: str,
    start_time: str,
    duration_minutes: int = 60,
    notes: str = ""
) -> str:
    """
    Schedule an interview with a candidate and interviewers.
    
    WHEN TO USE:
    - User wants to schedule an interview
    - User says "book an interview with [candidate] and [interviewers]"
    
    ARGS:
    - candidate_name (str): Name of the candidate being interviewed
    - interviewer_emails (List[str]): List of interviewer email addresses
    - date (str): The date in YYYY-MM-DD format
    - start_time (str): The start time in HH:MM format (24-hour)
    - duration_minutes (int): Interview length (default: 60)
    - notes (str): Optional notes about the interview
    
    RETURNS:
    - Confirmation message with interview details
    """
    logger.info(f"=== SCHEDULE INTERVIEW: {candidate_name} ===")
    logger.info(f"Interviewers: {interviewer_emails}")
    
    try:
        service = _get_calendar_service()
        tz = pytz.timezone(TIMEZONE)
        
        event_date = datetime.strptime(date, "%Y-%m-%d")
        hour, minute = map(int, start_time.split(":"))
        start_datetime = tz.localize(event_date.replace(hour=hour, minute=minute))
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        event = {
            "summary": f"Interview: {candidate_name}",
            "description": notes or f"Interview with {candidate_name}",
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
            "attendees": [{"email": email} for email in interviewer_emails],
        }
        
        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all",
        ).execute()
        
        logger.info(f"=== INTERVIEW SCHEDULED SUCCESSFULLY ===")
        
        return f"""✅ Interview scheduled!

👤 **Interview with {candidate_name}**
📅 {start_datetime.strftime('%A, %B %d, %Y')}
🕐 {start_datetime.strftime('%I:%M %p')} - {end_datetime.strftime('%I:%M %p')} ({duration_minutes} min)
👥 Interviewers: {', '.join(interviewer_emails)}

Calendar invites have been sent to all participants.
[View in Google Calendar]({created_event.get('htmlLink')})"""
        
    except Exception as e:
        logger.error(f"=== INTERVIEW SCHEDULING FAILED ===")
        logger.error(f"Error: {e}")
        return f"❌ Failed to schedule interview: {str(e)}"


# =========================
# Calendar Management Tools
# =========================

@tool
def delete_calendar_event(event_id: str) -> str:
    """
    Delete a calendar event by its ID.

    WHEN TO USE:
    - User wants to remove/cancel an event
    - User confirms they want to delete a specific event

    ARGS:
    - event_id (str): The Google Calendar event ID

    RETURNS:
    - Confirmation that the event was deleted
    """
    logger.info(f"=== DELETE EVENT: {event_id} ===")

    try:
        service = _get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()

        logger.info("Event deleted successfully")
        return "✅ Event deleted successfully."

    except Exception as e:
        logger.error(f"Failed to delete event: {e}")
        return f"❌ Failed to delete event: {str(e)}"


# =========================
# Email Tools
# =========================

@tool
def send_email(
    to_email: str,
    subject: str,
    body: str,
    cc: List[str] = None,
    bcc: List[str] = None
) -> str:
    """
    Send an email using Gmail SMTP.

    WHEN TO USE:
    - User asks to send an email
    - User wants to email someone with specific content
    - User says "email [person] about [topic]"

    ARGS:
    - to_email (str): Recipient's email address
    - subject (str): Email subject line
    - body (str): Email body content (can include line breaks)
    - cc (List[str]): Optional list of CC email addresses
    - bcc (List[str]): Optional list of BCC email addresses

    RETURNS:
    - Confirmation message with details of the sent email
    """
    logger.info(f"=== SEND EMAIL ===")
    logger.info(f"To: {to_email}")
    logger.info(f"Subject: {subject}")

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.error("Gmail credentials not configured")
        return "❌ Gmail credentials not configured. Please set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in your .env file."

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject

        if cc:
            msg['Cc'] = ', '.join(cc)

        # Add body
        msg.attach(MIMEText(body, 'plain'))

        # Build recipient list
        recipients = [to_email]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)

        # Connect to Gmail SMTP server
        logger.info("Connecting to Gmail SMTP server...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        logger.info("=== EMAIL SENT SUCCESSFULLY ===")

        result = f"""✅ Email sent successfully!

**To:** {to_email}
{f'**CC:** {", ".join(cc)}' if cc else ''}
**Subject:** {subject}

**Message:**
{body[:200]}{'...' if len(body) > 200 else ''}"""

        return result

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication failed")
        return "❌ Failed to send email: Gmail authentication failed. Please check your GMAIL_APP_PASSWORD."
    except Exception as e:
        logger.error(f"=== EMAIL SENDING FAILED ===")
        logger.error(f"Error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"❌ Failed to send email: {str(e)}"


# =========================
# Reminder Tools
# =========================

@tool
def get_reminders() -> str:
    """
    Get all daily reminders (personal and professional).

    WHEN TO USE:
    - User asks "what are my reminders?"
    - User wants to see their current reminders
    - You need to check existing reminders before adding a new one

    RETURNS:
    - A formatted string listing all personal and professional reminders
    """
    logger.info("=== GET REMINDERS ===")
    try:
        kb = _get_knowledge_base()
        reminders = kb.get_reminders()

        lines = []
        if reminders["professional"]:
            lines.append("**Professional:**")
            for i, r in enumerate(reminders["professional"]):
                lines.append(f"  {i + 1}. {r}")
        if reminders["personal"]:
            lines.append("**Personal:**")
            for i, r in enumerate(reminders["personal"]):
                lines.append(f"  {i + 1}. {r}")

        if not lines:
            return "No reminders set."

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Failed to get reminders: {e}")
        return f"Error getting reminders: {str(e)}"


@tool
def add_reminder(category: str, text: str) -> str:
    """
    Add a daily reminder.

    WHEN TO USE:
    - User says "remind me to ..." or "add a reminder for ..."
    - User wants to set a recurring daily reminder (personal or professional)

    ARGS:
    - category (str): "personal" or "professional"
    - text (str): The reminder text

    RETURNS:
    - Confirmation that the reminder was added
    """
    logger.info(f"=== ADD REMINDER: [{category}] {text} ===")
    try:
        kb = _get_knowledge_base()
        if kb.add_reminder(category, text):
            return f"✅ Added {category} reminder: {text}"
        return f"Reminder already exists or invalid category. Category must be 'personal' or 'professional'."

    except Exception as e:
        logger.error(f"Failed to add reminder: {e}")
        return f"Error adding reminder: {str(e)}"


@tool
def remove_reminder(category: str, index: int) -> str:
    """
    Remove a daily reminder by its position number.

    WHEN TO USE:
    - User wants to delete a specific reminder
    - User says "remove reminder #2" or "delete the first personal reminder"

    ARGS:
    - category (str): "personal" or "professional"
    - index (int): The 0-based index of the reminder to remove (first item = 0)

    RETURNS:
    - Confirmation that the reminder was removed
    """
    logger.info(f"=== REMOVE REMINDER: [{category}] index={index} ===")
    try:
        kb = _get_knowledge_base()
        if kb.remove_reminder(category, index):
            return f"✅ Removed {category} reminder at position {index + 1}."
        return f"Could not remove reminder. Check the category and position number."

    except Exception as e:
        logger.error(f"Failed to remove reminder: {e}")
        return f"Error removing reminder: {str(e)}"


# =========================
# Crucial Event Tools
# =========================

@tool
def get_crucial_events() -> str:
    """
    Get all crucial calendar events (birthdays, anniversaries, etc.).

    WHEN TO USE:
    - User asks "what crucial events do I have?" or "show my important dates"
    - You need to check existing crucial events

    RETURNS:
    - A formatted string listing all crucial events with their dates
    """
    logger.info("=== GET CRUCIAL EVENTS ===")
    try:
        kb = _get_knowledge_base()
        events = kb.get_crucial_events()

        if not events:
            return "No crucial events set."

        lines = ["**Crucial Events:**"]
        for i, e in enumerate(events):
            lines.append(f"  {i + 1}. {e['name']} — {e['date']}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Failed to get crucial events: {e}")
        return f"Error getting crucial events: {str(e)}"


@tool
def add_crucial_event(name: str, date: str) -> str:
    """
    Add a crucial calendar event (birthday, anniversary, holiday, etc.).
    These are recurring yearly all-day events that won't block meeting slots.

    WHEN TO USE:
    - User says "add my mom's birthday on January 21st"
    - User wants to track an important recurring date
    - User mentions a birthday, anniversary, or holiday to remember

    ARGS:
    - name (str): The event name (e.g. "Mom's Birthday", "Wedding Anniversary")
    - date (str): Date in MM-DD format for fixed dates (e.g. "01-21"),
                  or MM-Nth-sun for floating dates (e.g. "05-2nd-sun" for Mother's Day)

    RETURNS:
    - Confirmation that the crucial event was added
    """
    logger.info(f"=== ADD CRUCIAL EVENT: {name} on {date} ===")
    try:
        kb = _get_knowledge_base()
        if kb.add_crucial_event(name, date):
            return f"✅ Added crucial event: {name} on {date}"
        return f"Event '{name}' already exists."

    except Exception as e:
        logger.error(f"Failed to add crucial event: {e}")
        return f"Error adding crucial event: {str(e)}"


@tool
def remove_crucial_event(index: int) -> str:
    """
    Remove a crucial event by its position number.

    WHEN TO USE:
    - User wants to delete a crucial event
    - User says "remove crucial event #3"

    ARGS:
    - index (int): The 0-based index of the event to remove (first item = 0)

    RETURNS:
    - Confirmation that the event was removed
    """
    logger.info(f"=== REMOVE CRUCIAL EVENT: index={index} ===")
    try:
        kb = _get_knowledge_base()
        if kb.remove_crucial_event(index):
            return f"✅ Removed crucial event at position {index + 1}."
        return f"Could not remove event. Check the position number."

    except Exception as e:
        logger.error(f"Failed to remove crucial event: {e}")
        return f"Error removing crucial event: {str(e)}"


# =========================
# Daily Brief Tool
# =========================

# Module-level reference to the assistant instance (set by AIAssistant)
_assistant = None


def set_assistant(assistant):
    """Set the AIAssistant instance for the daily brief tool."""
    global _assistant
    _assistant = assistant


@tool
def generate_daily_brief() -> str:
    """
    Generate and return the user's daily brief.

    WHEN TO USE:
    - User asks for their daily brief or morning summary
    - User says "give me my brief", "daily update", "what's my day look like?"

    RETURNS:
    - A formatted daily brief with calendar highlights, reminders, and crucial events
    """
    logger.info("=== GENERATE DAILY BRIEF (from chat) ===")
    try:
        global _assistant
        if _assistant is None:
            return "Error: Assistant not initialized."
        return _assistant.generate_daily_brief()

    except Exception as e:
        logger.error(f"Failed to generate daily brief: {e}")
        return f"Error generating daily brief: {str(e)}"
