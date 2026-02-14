"""Knowledge base management for storing user prompts and memories."""
import random
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple

from src.database import (
    SessionLocal,
    KnowledgeBaseEntry,
    KnowledgeBaseBackup,
    Reminder,
    CrucialEvent,
)
from src.logging_utils import get_logger

logger = get_logger(__name__)


def resolve_crucial_event_date(date_str: str, year: int = None) -> Optional[str]:
    """Convert date string to YYYY-MM-DD. Handles MM-DD and MM-Nth-sun (e.g. 05-2nd-sun)."""
    year = year or datetime.now().year
    date_str = date_str.strip().lower()

    # Fixed: MM-DD
    match = re.match(r"^(\d{1,2})-(\d{1,2})$", date_str)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        try:
            d = datetime(year, month, day)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Floating: MM-Nth-sun (e.g. 05-2nd-sun, 06-3rd-sun)
    match = re.match(r"^(\d{1,2})-(\d+)(?:st|nd|rd|th)-sun$", date_str)
    if match:
        month = int(match.group(1))
        week_num = int(match.group(2))  # 1st, 2nd, 3rd, etc.
        # Find Nth Sunday of month (weekday 6 = Sunday in Python)
        first = datetime(year, month, 1)
        days_until_first_sunday = (6 - first.weekday()) % 7
        if first.weekday() == 6:
            days_until_first_sunday = 0  # First day is Sunday
        first_sunday_day = 1 + days_until_first_sunday
        nth_sunday_day = first_sunday_day + (week_num - 1) * 7
        try:
            d = datetime(year, month, nth_sunday_day)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


DEFAULT_KB_TEMPLATE = """# Personal Knowledge Base

## About Me
<!-- Add information about yourself that the assistant should know -->
I like efficiency and impact.

## Work Context
<!-- Add context about your work that helps with scheduling and reminders -->
1. I'm the head of data at a startup called Stan.

## Preferences
<!-- Add your preferences for reminders, scheduling, etc. -->
1. I like 30 minute meetings by default.


"""

DEFAULT_CRUCIAL_EVENTS = [
    {"name": "Valentine's Day", "date": "02-14"},
    {"name": "Father's Day", "date": "06-3rd-sun"},
    {"name": "Mother's Day", "date": "05-2nd-sun"},
]


class KnowledgeBase:
    """Manages the knowledge base - a markdown-based memory system."""

    def __init__(self, user_email: str):
        """Initialize knowledge base for a user."""
        logger.info(f"Initializing knowledge base for: {user_email}")
        self.user_email = user_email

        with SessionLocal() as session:
            # Initialize KB entry if missing
            kb = session.query(KnowledgeBaseEntry).filter_by(user_email=user_email).first()
            if not kb:
                logger.info("Knowledge base not found, creating from template")
                self._init_knowledge_base(session)

            # Initialize crucial events if none exist
            has_events = session.query(CrucialEvent).filter_by(user_email=user_email).first()
            if not has_events:
                logger.info("Crucial events not found, creating defaults")
                self._init_crucial_events(session)

            session.commit()

    def _init_knowledge_base(self, session):
        """Initialize the knowledge base with a template."""
        session.add(KnowledgeBaseEntry(
            user_email=self.user_email,
            content=DEFAULT_KB_TEMPLATE,
        ))

    def _init_crucial_events(self, session):
        """Initialize crucial calendar events (all-day, recurring, won't block meetings)."""
        for event in DEFAULT_CRUCIAL_EVENTS:
            session.add(CrucialEvent(
                user_email=self.user_email,
                name=event["name"],
                date=event["date"],
            ))

    def get_knowledge_base(self) -> str:
        """Get the full knowledge base content."""
        with SessionLocal() as session:
            kb = session.query(KnowledgeBaseEntry).filter_by(user_email=self.user_email).first()
            if kb:
                logger.info(f"Knowledge base loaded ({len(kb.content)} chars)")
                return kb.content
        logger.warning("Knowledge base entry not found")
        return ""

    def update_knowledge_base(self, content: str) -> bool:
        """Update the entire knowledge base content."""
        logger.info(f"Updating knowledge base ({len(content)} chars)")
        try:
            with SessionLocal() as session:
                kb = session.query(KnowledgeBaseEntry).filter_by(user_email=self.user_email).first()

                # Create backup of current content
                if kb:
                    session.add(KnowledgeBaseBackup(
                        user_email=self.user_email,
                        content=kb.content,
                    ))
                    kb.content = content
                else:
                    session.add(KnowledgeBaseEntry(
                        user_email=self.user_email,
                        content=content,
                    ))

                session.commit()
            logger.info("Knowledge base updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating knowledge base: {e}")
            return False

    def append_to_knowledge_base(self, section: str, content: str) -> bool:
        """Append content to a specific section of the knowledge base."""
        try:
            kb_content = self.get_knowledge_base()

            # Find the section
            section_header = f"## {section}"
            if section_header in kb_content:
                # Find the next section or end of file
                section_start = kb_content.find(section_header)
                next_section = kb_content.find("\n## ", section_start + len(section_header))

                if next_section == -1:
                    # Append to end
                    new_content = kb_content + f"\n{content}\n"
                else:
                    # Insert before next section
                    new_content = (
                        kb_content[:next_section] +
                        f"\n{content}\n" +
                        kb_content[next_section:]
                    )
            else:
                # Add new section
                new_content = kb_content + f"\n{section_header}\n{content}\n"

            return self.update_knowledge_base(new_content)
        except Exception as e:
            print(f"Error appending to knowledge base: {e}")
            return False

    def get_reminders(self) -> Dict[str, List[str]]:
        """Get all daily reminders (personal + professional)."""
        with SessionLocal() as session:
            rows = session.query(Reminder).filter_by(user_email=self.user_email).all()
            result: Dict[str, List[str]] = {"personal": [], "professional": []}
            for row in rows:
                if row.category in result:
                    result[row.category].append(row.text)
            return result

    def add_reminder(self, category: str, text: str) -> bool:
        """Add a reminder (category: 'personal' or 'professional')."""
        if category not in ("personal", "professional"):
            return False
        try:
            text = text.strip()
            if not text:
                return False
            with SessionLocal() as session:
                exists = (
                    session.query(Reminder)
                    .filter_by(user_email=self.user_email, category=category, text=text)
                    .first()
                )
                if exists:
                    return False
                session.add(Reminder(
                    user_email=self.user_email,
                    category=category,
                    text=text,
                ))
                session.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return False

    def remove_reminder(self, category: str, index: int) -> bool:
        """Remove a reminder by index."""
        if category not in ("personal", "professional"):
            return False
        try:
            with SessionLocal() as session:
                rows = (
                    session.query(Reminder)
                    .filter_by(user_email=self.user_email, category=category)
                    .order_by(Reminder.id)
                    .all()
                )
                if 0 <= index < len(rows):
                    session.delete(rows[index])
                    session.commit()
                    return True
            return False
        except Exception as e:
            logger.error(f"Error removing reminder: {e}")
            return False

    def get_random_daily_reminders(self) -> Tuple[Optional[str], Optional[str]]:
        """Pick one random personal and one random professional reminder for the brief."""
        reminders = self.get_reminders()
        personal = random.choice(reminders["personal"]) if reminders["personal"] else None
        professional = random.choice(reminders["professional"]) if reminders["professional"] else None
        return personal, professional

    def get_crucial_events(self) -> List[Dict[str, str]]:
        """Get crucial calendar events."""
        with SessionLocal() as session:
            rows = (
                session.query(CrucialEvent)
                .filter_by(user_email=self.user_email)
                .order_by(CrucialEvent.id)
                .all()
            )
            return [{"name": r.name, "date": r.date} for r in rows]

    def add_crucial_event(self, name: str, date: str) -> bool:
        """Add a crucial event. Date: MM-DD for fixed, or MM-Nth-sun for floating (e.g. 05-2nd-sun)."""
        try:
            with SessionLocal() as session:
                exists = (
                    session.query(CrucialEvent)
                    .filter_by(user_email=self.user_email, name=name)
                    .first()
                )
                if exists:
                    return False
                session.add(CrucialEvent(
                    user_email=self.user_email,
                    name=name,
                    date=date,
                ))
                session.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding crucial event: {e}")
            return False

    def remove_crucial_event(self, index: int) -> bool:
        """Remove crucial event by index."""
        try:
            with SessionLocal() as session:
                rows = (
                    session.query(CrucialEvent)
                    .filter_by(user_email=self.user_email)
                    .order_by(CrucialEvent.id)
                    .all()
                )
                if 0 <= index < len(rows):
                    session.delete(rows[index])
                    session.commit()
                    return True
            return False
        except Exception as e:
            logger.error(f"Error removing crucial event: {e}")
            return False

    def get_daily_brief_context(self) -> str:
        """Get knowledge base content for context (reminders are separate, managed in Daily Brief settings)."""
        return self.get_knowledge_base()

    def search_knowledge_base(self, query: str) -> List[str]:
        """Search the knowledge base for relevant content."""
        kb_content = self.get_knowledge_base()
        lines = kb_content.split("\n")

        results = []
        for i, line in enumerate(lines):
            if query.lower() in line.lower():
                # Include some context
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context = "\n".join(lines[start:end])
                results.append(context)

        return results
