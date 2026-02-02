"""Google Calendar integration service."""

from datetime import datetime, timedelta
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz

from src.config import TIMEZONE


class CalendarService:
    """Service for interacting with Google Calendar."""
    
    def __init__(self, credentials: Credentials):
        """Initialize the calendar service with credentials."""
        self.service = build("calendar", "v3", credentials=credentials)
        self.timezone = pytz.timezone(TIMEZONE)
    
    def get_upcoming_events(self, days: int = 7, max_results: int = 50) -> list[dict]:
        """Get upcoming events for the next N days."""
        now = datetime.now(self.timezone)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days)).isoformat()
        
        try:
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            
            events = events_result.get("items", [])
            return self._format_events(events)
        except HttpError as e:
            print(f"Error fetching events: {e}")
            return []
    
    def get_todays_events(self) -> list[dict]:
        """Get all events for today."""
        now = datetime.now(self.timezone)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        try:
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            
            events = events_result.get("items", [])
            return self._format_events(events)
        except HttpError as e:
            print(f"Error fetching today's events: {e}")
            return []
    
    def create_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        attendees: list[str] = None,
        recurrence: list[str] = None,
        location: str = "",
    ) -> dict | None:
        """Create a new calendar event."""
        event = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": TIMEZONE,
            },
        }
        
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        
        if recurrence:
            event["recurrence"] = recurrence
        
        try:
            created_event = self.service.events().insert(
                calendarId="primary",
                body=event,
                sendUpdates="all" if attendees else "none",
            ).execute()
            return created_event
        except HttpError as e:
            print(f"Error creating event: {e}")
            return None
    
    def create_recurring_birthday(
        self,
        name: str,
        month: int,
        day: int,
        notes: str = "",
    ) -> dict | None:
        """Create a recurring yearly birthday event."""
        # Create the first occurrence
        year = datetime.now().year
        # If the date has passed this year, start next year
        today = datetime.now().date()
        birthday_date = datetime(year, month, day).date()
        if birthday_date < today:
            year += 1
        
        start_time = datetime(year, month, day, 9, 0, 0, tzinfo=self.timezone)
        end_time = start_time + timedelta(hours=1)
        
        return self.create_event(
            summary=f"🎂 {name}'s Birthday",
            start_time=start_time,
            end_time=end_time,
            description=notes,
            recurrence=["RRULE:FREQ=YEARLY"],
        )
    
    def create_interview(
        self,
        candidate_name: str,
        interviewers: list[str],
        start_time: datetime,
        duration_minutes: int = 60,
        interview_type: str = "Interview",
        notes: str = "",
    ) -> dict | None:
        """Create an interview event with attendees."""
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        return self.create_event(
            summary=f"{interview_type}: {candidate_name}",
            start_time=start_time,
            end_time=end_time,
            description=notes,
            attendees=interviewers,
        )
    
    def find_free_slots(
        self,
        duration_minutes: int = 60,
        days_ahead: int = 7,
        working_hours: tuple[int, int] = (9, 17),
    ) -> list[dict]:
        """Find free time slots in the calendar."""
        now = datetime.now(self.timezone)
        end_date = now + timedelta(days=days_ahead)
        
        # Get all events in the time range
        events = self.get_upcoming_events(days=days_ahead, max_results=100)
        
        free_slots = []
        current_date = now.date()
        
        while current_date <= end_date.date():
            day_start = datetime.combine(
                current_date,
                datetime.min.time().replace(hour=working_hours[0]),
                tzinfo=self.timezone,
            )
            day_end = datetime.combine(
                current_date,
                datetime.min.time().replace(hour=working_hours[1]),
                tzinfo=self.timezone,
            )
            
            # Skip if in the past
            if day_end < now:
                current_date += timedelta(days=1)
                continue
            
            # Adjust start if today
            if current_date == now.date():
                day_start = max(day_start, now)
            
            # Get events for this day
            day_events = [
                e for e in events
                if e.get("start_datetime") and 
                e["start_datetime"].date() == current_date
            ]
            
            # Sort by start time
            day_events.sort(key=lambda x: x.get("start_datetime", day_end))
            
            # Find gaps
            current_time = day_start
            for event in day_events:
                event_start = event.get("start_datetime")
                event_end = event.get("end_datetime")
                
                if event_start and current_time + timedelta(minutes=duration_minutes) <= event_start:
                    free_slots.append({
                        "start": current_time,
                        "end": event_start,
                        "duration_minutes": int((event_start - current_time).total_seconds() / 60),
                    })
                
                if event_end:
                    current_time = max(current_time, event_end)
            
            # Check remaining time after last event
            if current_time + timedelta(minutes=duration_minutes) <= day_end:
                free_slots.append({
                    "start": current_time,
                    "end": day_end,
                    "duration_minutes": int((day_end - current_time).total_seconds() / 60),
                })
            
            current_date += timedelta(days=1)
        
        return free_slots
    
    def _format_events(self, events: list) -> list[dict]:
        """Format raw calendar events into a cleaner structure."""
        formatted = []
        for event in events:
            start = event.get("start", {})
            end = event.get("end", {})
            
            # Handle all-day events vs timed events
            if "dateTime" in start:
                start_dt = datetime.fromisoformat(start["dateTime"])
                end_dt = datetime.fromisoformat(end["dateTime"])
                all_day = False
            else:
                start_dt = datetime.strptime(start.get("date", ""), "%Y-%m-%d")
                end_dt = datetime.strptime(end.get("date", ""), "%Y-%m-%d")
                all_day = True
            
            formatted.append({
                "id": event.get("id"),
                "summary": event.get("summary", "No Title"),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "start_datetime": start_dt,
                "end_datetime": end_dt,
                "all_day": all_day,
                "attendees": [
                    a.get("email") for a in event.get("attendees", [])
                ],
                "html_link": event.get("htmlLink"),
            })
        
        return formatted
    
    def get_calendar_summary(self, days: int = 7) -> str:
        """Get a text summary of upcoming events."""
        events = self.get_upcoming_events(days=days)
        
        if not events:
            return f"No events in the next {days} days."
        
        summary_lines = [f"📅 Upcoming events (next {days} days):\n"]
        
        current_date = None
        for event in events:
            event_date = event["start_datetime"].date()
            
            if event_date != current_date:
                current_date = event_date
                summary_lines.append(f"\n**{event_date.strftime('%A, %B %d')}**")
            
            if event["all_day"]:
                time_str = "All day"
            else:
                time_str = event["start_datetime"].strftime("%I:%M %p")
            
            summary_lines.append(f"  • {time_str}: {event['summary']}")
        
        return "\n".join(summary_lines)
