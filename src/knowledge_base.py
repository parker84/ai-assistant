"""Knowledge base management for storing user prompts and memories."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.config import DATA_DIR, KNOWLEDGE_BASE_PATH
from src.logging_utils import get_logger

logger = get_logger(__name__)


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
        
        logger.info(f"Knowledge base path: {self.kb_file}")
        
        # Initialize files if they don't exist
        if not self.kb_file.exists():
            logger.info("Knowledge base file not found, creating from template")
            self._init_knowledge_base()
        if not self.reminders_file.exists():
            logger.info("Reminders file not found, creating empty")
            self._init_reminders()
    
    def _init_knowledge_base(self):
        """Initialize the knowledge base with a template."""
        template = """# Personal Knowledge Base

## About Me
<!-- Add information about yourself that the assistant should know -->


## Important People
<!-- Add information about important people in your life -->
<!-- Example:
- **Mom (Jane)**: Birthday March 15, loves gardening
- **Partner (Alex)**: Anniversary June 20, allergic to shellfish
-->


## Work Context
<!-- Add context about your work that helps with scheduling and reminders -->


## Preferences
<!-- Add your preferences for reminders, scheduling, etc. -->


## Custom Reminders
<!-- Add any recurring reminders or things you want to remember -->


## Notes
<!-- General notes and information -->

"""
        self.kb_file.write_text(template)
    
    def _init_reminders(self):
        """Initialize the reminders file."""
        initial_reminders = {
            "daily_reminders": [],
            "recurring_reminders": [],
            "one_time_reminders": [],
        }
        with open(self.reminders_file, "w") as f:
            json.dump(initial_reminders, f, indent=2)
    
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
    
    def get_reminders(self) -> Dict[str, Any]:
        """Get all reminders."""
        if self.reminders_file.exists():
            with open(self.reminders_file, "r") as f:
                return json.load(f)
        return {"daily_reminders": [], "recurring_reminders": [], "one_time_reminders": []}
    
    def add_reminder(
        self,
        text: str,
        reminder_type: str = "daily",
        schedule: Optional[Dict] = None,
    ) -> bool:
        """Add a new reminder."""
        try:
            reminders = self.get_reminders()
            
            reminder = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "text": text,
                "created_at": datetime.now().isoformat(),
                "schedule": schedule,
            }
            
            if reminder_type == "daily":
                reminders["daily_reminders"].append(reminder)
            elif reminder_type == "recurring":
                reminders["recurring_reminders"].append(reminder)
            else:
                reminders["one_time_reminders"].append(reminder)
            
            with open(self.reminders_file, "w") as f:
                json.dump(reminders, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error adding reminder: {e}")
            return False
    
    def remove_reminder(self, reminder_id: str) -> bool:
        """Remove a reminder by ID."""
        try:
            reminders = self.get_reminders()
            
            for reminder_type in ["daily_reminders", "recurring_reminders", "one_time_reminders"]:
                reminders[reminder_type] = [
                    r for r in reminders[reminder_type] if r["id"] != reminder_id
                ]
            
            with open(self.reminders_file, "w") as f:
                json.dump(reminders, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error removing reminder: {e}")
            return False
    
    def get_daily_brief_context(self) -> str:
        """Get context for generating the daily brief."""
        kb_content = self.get_knowledge_base()
        reminders = self.get_reminders()
        
        context = f"""
## Knowledge Base
{kb_content}

## Custom Reminders
### Daily Reminders
{json.dumps(reminders.get('daily_reminders', []), indent=2)}

### Recurring Reminders
{json.dumps(reminders.get('recurring_reminders', []), indent=2)}
"""
        return context
    
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
