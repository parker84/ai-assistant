"""Google Calendar integration."""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import pytz

from src.config import TIMEZONE


def get_calendar_service(credentials: Credentials):
    """Build Google Calendar service."""
    return build("calendar", "v3", credentials=credentials)


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
    service = get_calendar_service(credentials)
    tz = pytz.timezone(TIMEZONE)
    
    # Ensure timezone awareness
    if start_time.tzinfo is None:
        start_time = tz.localize(start_time)
    if end_time.tzinfo is None:
        end_time = tz.localize(end_time)
    
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
    
    created_event = service.events().insert(
        calendarId="primary",
        body=event,
        sendUpdates="all" if attendees else "none",
    ).execute()
    
    return created_event


def create_recurring_birthday(
    credentials: Credentials,
    name: str,
    birthday_date: datetime,
    reminder_days_before: int = 1,
) -> Dict[str, Any]:
    """Create a recurring yearly birthday event."""
    tz = pytz.timezone(TIMEZONE)
    
    # Set to all-day event
    start_date = birthday_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=1)
    
    # Yearly recurrence
    recurrence = ["RRULE:FREQ=YEARLY"]
    
    event = create_event(
        credentials=credentials,
        summary=f"🎂 {name}'s Birthday",
        start_time=start_date,
        end_time=end_date,
        description=f"Don't forget to wish {name} a happy birthday!",
        recurrence=recurrence,
    )
    
    return event


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
