"""Google Calendar integration."""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import pytz

from src.config import TIMEZONE
from src.logging_utils import get_logger

logger = get_logger(__name__)


def get_calendar_service(credentials: Credentials):
    """Build Google Calendar service."""
    logger.debug("Building Google Calendar service...")
    try:
        service = build("calendar", "v3", credentials=credentials)
        logger.debug("Calendar service built successfully")
        return service
    except Exception as e:
        logger.error(f"Failed to build calendar service: {e}")
        raise


def get_todays_events(credentials: Credentials) -> List[Dict[str, Any]]:
    """Get all events for today."""
    service = get_calendar_service(credentials)
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
    
    return events_result.get("items", [])


def get_upcoming_events(credentials: Credentials, days: int = 7) -> List[Dict[str, Any]]:
    """Get upcoming events for the next N days."""
    service = get_calendar_service(credentials)
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
    
    return events_result.get("items", [])


def get_events_in_range(
    credentials: Credentials,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """Get events within a specific date range."""
    service = get_calendar_service(credentials)
    tz = pytz.timezone(TIMEZONE)
    
    # Ensure timezone awareness
    if start_date.tzinfo is None:
        start_date = tz.localize(start_date)
    if end_date.tzinfo is None:
        end_date = tz.localize(end_date)
    
    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_date.isoformat(),
        timeMax=end_date.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    
    return events_result.get("items", [])


def create_event(
    credentials: Credentials,
    summary: str,
    start_time: datetime,
    end_time: datetime,
    description: str = "",
    attendees: List[str] = None,
    recurrence: List[str] = None,
    location: str = "",
) -> Dict[str, Any]:
    """Create a new calendar event."""
    logger.info(f"=== CREATE EVENT START ===")
    logger.info(f"Summary: {summary}")
    logger.info(f"Start: {start_time}")
    logger.info(f"End: {end_time}")
    logger.info(f"Attendees: {attendees}")
    logger.info(f"Recurrence: {recurrence}")
    
    try:
        service = get_calendar_service(credentials)
        tz = pytz.timezone(TIMEZONE)
        
        # Ensure timezone awareness
        if start_time.tzinfo is None:
            start_time = tz.localize(start_time)
            logger.debug(f"Localized start_time to: {start_time}")
        if end_time.tzinfo is None:
            end_time = tz.localize(end_time)
            logger.debug(f"Localized end_time to: {end_time}")
        
        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": TIMEZONE,
            },
        }
        
        if location:
            event["location"] = location
        
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        
        if recurrence:
            event["recurrence"] = recurrence
        
        logger.info(f"Event payload: {event}")
        logger.info("Calling Google Calendar API to insert event...")
        
        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all" if attendees else "none",
        ).execute()
        
        logger.info(f"=== EVENT CREATED SUCCESSFULLY ===")
        logger.info(f"Event ID: {created_event.get('id')}")
        logger.info(f"Event link: {created_event.get('htmlLink')}")
        logger.info(f"Full response: {created_event}")
        
        return created_event
        
    except Exception as e:
        logger.error(f"=== EVENT CREATION FAILED ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to create event '{summary}': {str(e)}")


def create_recurring_birthday(
    credentials: Credentials,
    name: str,
    birthday_date: datetime,
    reminder_days_before: int = 1,
) -> Dict[str, Any]:
    """Create a recurring yearly birthday event as an all-day event."""
    logger.info(f"=== CREATE BIRTHDAY START ===")
    logger.info(f"Name: {name}")
    logger.info(f"Birthday date: {birthday_date}")
    
    try:
        service = get_calendar_service(credentials)
        
        # Format as date string for all-day event
        start_date_str = birthday_date.strftime("%Y-%m-%d")
        end_date = birthday_date + timedelta(days=1)
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        logger.info(f"Start date (all-day): {start_date_str}")
        logger.info(f"End date (all-day): {end_date_str}")
        
        # Yearly recurrence
        recurrence = ["RRULE:FREQ=YEARLY"]
        
        event = {
            "summary": f"🎂 {name}'s Birthday",
            "description": f"Don't forget to wish {name} a happy birthday!",
            "start": {
                "date": start_date_str,
            },
            "end": {
                "date": end_date_str,
            },
            "recurrence": recurrence,
        }
        
        logger.info(f"Birthday event payload: {event}")
        logger.info("Calling Google Calendar API to insert birthday...")
        
        created_event = service.events().insert(
            calendarId="primary",
            body=event,
        ).execute()
        
        logger.info(f"=== BIRTHDAY CREATED SUCCESSFULLY ===")
        logger.info(f"Event ID: {created_event.get('id')}")
        logger.info(f"Event link: {created_event.get('htmlLink')}")
        
        return created_event
        
    except Exception as e:
        logger.error(f"=== BIRTHDAY CREATION FAILED ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to create birthday for '{name}': {str(e)}")


def create_interview_event(
    credentials: Credentials,
    candidate_name: str,
    interviewers: List[str],
    start_time: datetime,
    duration_minutes: int = 60,
    description: str = "",
) -> Dict[str, Any]:
    """Create an interview event with multiple attendees."""
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    event = create_event(
        credentials=credentials,
        summary=f"Interview: {candidate_name}",
        start_time=start_time,
        end_time=end_time,
        description=description or f"Interview with {candidate_name}",
        attendees=interviewers,
    )
    
    return event


def find_free_slots(
    credentials: Credentials,
    date: datetime,
    duration_minutes: int = 60,
    working_hours: tuple = (9, 17),
) -> List[Dict[str, datetime]]:
    """Find available time slots on a given day."""
    service = get_calendar_service(credentials)
    tz = pytz.timezone(TIMEZONE)
    
    # Set up the day's boundaries
    if date.tzinfo is None:
        date = tz.localize(date)
    
    start_of_day = date.replace(hour=working_hours[0], minute=0, second=0, microsecond=0)
    end_of_day = date.replace(hour=working_hours[1], minute=0, second=0, microsecond=0)
    
    # Get existing events
    events = get_events_in_range(credentials, start_of_day, end_of_day)
    
    # Find free slots
    free_slots = []
    current_time = start_of_day
    
    for event in events:
        event_start_str = event.get("start", {}).get("dateTime")
        event_end_str = event.get("end", {}).get("dateTime")
        
        if not event_start_str or not event_end_str:
            continue
        
        event_start = datetime.fromisoformat(event_start_str.replace("Z", "+00:00"))
        event_end = datetime.fromisoformat(event_end_str.replace("Z", "+00:00"))
        
        # Convert to local timezone
        event_start = event_start.astimezone(tz)
        event_end = event_end.astimezone(tz)
        
        # Check if there's a free slot before this event
        if current_time + timedelta(minutes=duration_minutes) <= event_start:
            free_slots.append({
                "start": current_time,
                "end": event_start,
            })
        
        # Move current time to after this event
        if event_end > current_time:
            current_time = event_end
    
    # Check for free time after the last event
    if current_time + timedelta(minutes=duration_minutes) <= end_of_day:
        free_slots.append({
            "start": current_time,
            "end": end_of_day,
        })
    
    return free_slots


def delete_event(credentials: Credentials, event_id: str) -> bool:
    """Delete a calendar event."""
    service = get_calendar_service(credentials)
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True
    except Exception:
        return False


def update_event(
    credentials: Credentials,
    event_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update an existing calendar event."""
    service = get_calendar_service(credentials)
    
    try:
        # Get the existing event
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        
        # Apply updates
        event.update(updates)
        
        # Update the event
        updated_event = service.events().update(
            calendarId="primary",
            eventId=event_id,
            body=event,
        ).execute()
        
        return updated_event
    except Exception:
        return None


def format_event_for_display(event: Dict[str, Any]) -> str:
    """Format an event for display."""
    summary = event.get("summary", "No title")
    
    start = event.get("start", {})
    if "dateTime" in start:
        start_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
        time_str = start_time.strftime("%I:%M %p")
    else:
        time_str = "All day"
    
    location = event.get("location", "")
    location_str = f" @ {location}" if location else ""
    
    return f"• {time_str}: {summary}{location_str}"


def get_calendar_summary(credentials: Credentials, days: int = 7) -> str:
    """Get a text summary of upcoming events."""
    events = get_upcoming_events(credentials, days)
    
    if not events:
        return "No upcoming events in the next week."
    
    lines = [f"📅 Upcoming Events ({days} days):"]
    
    current_date = None
    for event in events:
        start = event.get("start", {})
        if "dateTime" in start:
            event_date = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
        else:
            event_date = datetime.fromisoformat(start.get("date", ""))
        
        # Add date header if new day
        date_str = event_date.strftime("%A, %B %d")
        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n**{date_str}**")
        
        lines.append(format_event_for_display(event))
    
    return "\n".join(lines)
