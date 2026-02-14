"""Knowledge base management for storing user prompts and memories."""
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from src.config import DATA_DIR, KNOWLEDGE_BASE_PATH
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


class KnowledgeBase:
    """Manages the knowledge base - a markdown-based memory system."""
    
    def __init__(self, user_email: str):
        """Initialize knowledge base for a user."""
        logger.info(f"Initializing knowledge base for: {user_email}")
        
        self.user_email = user_email
        self.user_dir = DATA_DIR / "users" / user_email.replace("@", "_at_").replace(".", "_")
        self.user_dir.mkdir(parents=True, exist_ok=True)
        
        self.kb_file = self.user_dir / "knowledge_base.md"
        self.reminders_file = self.user_dir / "reminders.json"
        self.crucial_events_file = self.user_dir / "crucial_events.json"
        
        logger.info(f"Knowledge base path: {self.kb_file}")
        
        # Initialize files if they don't exist
        if not self.kb_file.exists():
            logger.info("Knowledge base file not found, creating from template")
            self._init_knowledge_base()
        if not self.reminders_file.exists():
            logger.info("Reminders file not found, creating empty")
            self._init_reminders()
        if not self.crucial_events_file.exists():
            logger.info("Crucial events file not found, creating with defaults")
            self._init_crucial_events()
    
    def _init_knowledge_base(self):
        """Initialize the knowledge base with a template."""
        template = """# Personal Knowledge Base

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
        self.kb_file.write_text(template)
    
    def _init_reminders(self):
        """Initialize the reminders file (personal + professional for daily brief)."""
        initial_reminders = {
            "personal": [],
            "professional": [],
        }
        with open(self.reminders_file, "w") as f:
            json.dump(initial_reminders, f, indent=2)

    def _init_crucial_events(self):
        """Initialize crucial calendar events (all-day, recurring, won't block meetings)."""
        default_events = [
            {"name": "Paul's Birthday", "date": "02-05"},
            {"name": "Mom's Birthday", "date": "01-21"},
            {"name": "Anniversary", "date": "01-23"},
            {"name": "Wedding Anniversary", "date": "06-26"},
            {"name": "Kennedy Birthday", "date": "09-20"},
            {"name": "Valentine's Day", "date": "02-14"},
            {"name": "Shaun's Birthday", "date": "03-01"},
            {"name": "Maddy's Birthday", "date": "10-09"},
            {"name": "Dad's Birthday", "date": "11-26"},
            {"name": "Father's Day", "date": "06-3rd-sun"},
            {"name": "Mother's Day", "date": "05-2nd-sun"},
        ]
        self.crucial_events_file.write_text(json.dumps({"events": default_events}, indent=2))
    
    def get_knowledge_base(self) -> str:
        """Get the full knowledge base content."""
        if self.kb_file.exists():
            content = self.kb_file.read_text()
            logger.info(f"Knowledge base loaded ({len(content)} chars)")
            return content
        logger.warning("Knowledge base file not found")
        return ""
    
    def update_knowledge_base(self, content: str) -> bool:
        """Update the entire knowledge base content."""
        logger.info(f"Updating knowledge base ({len(content)} chars)")
        try:
            # Create backup
            if self.kb_file.exists():
                backup_file = self.user_dir / f"knowledge_base_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                backup_file.write_text(self.kb_file.read_text())
                logger.info(f"Backup created: {backup_file.name}")
            
            self.kb_file.write_text(content)
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
        if self.reminders_file.exists():
            try:
                data = json.loads(self.reminders_file.read_text())
                # Migrate old format to new
                if "daily_reminders" in data:
                    # Migrate: extract text from old reminder objects
                    personal = []
                    professional = []
                    for r in data.get("daily_reminders", []):
                        text = r.get("text", "") if isinstance(r, dict) else str(r)
                        if text:
                            professional.append(text)  # Default old daily to professional
                    migrated = {"personal": personal, "professional": professional}
                    self.reminders_file.write_text(json.dumps(migrated, indent=2))
                    return migrated
                if "personal" in data or "professional" in data:
                    return {
                        "personal": data.get("personal", []),
                        "professional": data.get("professional", []),
                    }
            except (json.JSONDecodeError, TypeError):
                pass
        return {"personal": [], "professional": []}

    def add_reminder(self, category: str, text: str) -> bool:
        """Add a reminder (category: 'personal' or 'professional')."""
        if category not in ("personal", "professional"):
            return False
        try:
            reminders = self.get_reminders()
            text = text.strip()
            if text and text not in reminders[category]:
                reminders[category].append(text)
                self.reminders_file.write_text(json.dumps(reminders, indent=2))
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return False

    def remove_reminder(self, category: str, index: int) -> bool:
        """Remove a reminder by index."""
        if category not in ("personal", "professional"):
            return False
        try:
            reminders = self.get_reminders()
            if 0 <= index < len(reminders[category]):
                reminders[category].pop(index)
                self.reminders_file.write_text(json.dumps(reminders, indent=2))
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
        if self.crucial_events_file.exists():
            try:
                data = json.loads(self.crucial_events_file.read_text())
                return data.get("events", [])
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    def add_crucial_event(self, name: str, date: str) -> bool:
        """Add a crucial event. Date: MM-DD for fixed, or MM-Nth-sun for floating (e.g. 05-2nd-sun)."""
        try:
            events = self.get_crucial_events()
            if any(e["name"] == name for e in events):
                return False
            events.append({"name": name, "date": date})
            self.crucial_events_file.write_text(json.dumps({"events": events}, indent=2))
            return True
        except Exception as e:
            logger.error(f"Error adding crucial event: {e}")
            return False

    def remove_crucial_event(self, index: int) -> bool:
        """Remove crucial event by index."""
        try:
            events = self.get_crucial_events()
            if 0 <= index < len(events):
                events.pop(index)
                self.crucial_events_file.write_text(json.dumps({"events": events}, indent=2))
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
