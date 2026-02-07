"""AI Assistant using Agno framework."""
from textwrap import dedent
from typing import Optional
from datetime import datetime
import pytz
from agno.db.postgres import PostgresDb
from decouple import config
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude

from src.config import (
    LLM_PROVIDER,
    LLM_MODEL,
    TIMEZONE,
)
from src.knowledge_base import KnowledgeBase
from src.logging_utils import get_logger
from src.tools import (
    set_credentials,
    get_todays_events,
    get_upcoming_events,
    find_free_time_slots,
    create_calendar_event,
    create_birthday_reminder,
    schedule_interview,
    delete_calendar_event,
    send_email,
)

logger = get_logger(__name__)

# Agent configuration
MAX_TOOL_CALLS = 5
NUM_HISTORY_RUNS = 10


def get_llm_model():
    """Get the configured LLM model based on provider."""
    logger.info(f"Initializing LLM: {LLM_PROVIDER}/{LLM_MODEL}")
    
    if LLM_PROVIDER == "openai":
        return OpenAIChat(id=LLM_MODEL)
    elif LLM_PROVIDER == "anthropic":
        return Claude(id=LLM_MODEL)
    else:
        # Default to OpenAI
        logger.warning(f"Unknown provider {LLM_PROVIDER}, defaulting to OpenAI")
        return OpenAIChat(id="gpt-4o-mini")

# ------------database / storage / setup
db_url = f"postgresql+psycopg://{config('POSTGRES_USER')}:{config('POSTGRES_PASSWORD')}@{config('POSTGRES_HOST')}/{config('POSTGRES_DB')}"

team_storage = PostgresDb(
    db_url=db_url
)

ASSISTANT_INSTRUCTIONS = dedent("""
    You are a helpful personal AI assistant that helps users manage their calendar, send emails, and stay organized.

    You have access to the user's Google Calendar and Gmail. Use them to:
    - View today's events and upcoming schedule
    - Create new events, meetings, and reminders
    - Schedule interviews with multiple participants
    - Add birthday reminders that recur yearly
    - Find available time slots for scheduling
    - Send emails on behalf of the user
    
    IMPORTANT GUIDELINES:
    
    1. **Before creating events**: Always confirm the details with the user first.
       - Ask for missing information (date, time, duration)
       - Clarify ambiguous requests
    
    2. **Date/Time handling**: 
       - When the user says "tomorrow", "next Monday", etc., calculate the actual date
       - Use 24-hour format (HH:MM) for the tools
       - Default duration is 60 minutes unless specified
    
    3. **Be helpful and proactive**:
       - If the user's calendar looks busy, mention it
       - Suggest optimal times based on their schedule
       - Remind them of potential conflicts
    
    4. **Knowledge Base**:
       - Reference the user's knowledge base for context about important people, preferences
       - Use this context to personalize your responses
    
    5. **Response format**:
       - Be concise but friendly
       - Use emojis sparingly for visual clarity
       - When showing calendar info, format it nicely
""")


class AIAssistant:
    """Agno-powered AI Assistant for calendar and task management."""
    
    def __init__(self, user_email: str, credentials=None):
        """Initialize the assistant for a user."""
        logger.info(f"=== INITIALIZING AGNO ASSISTANT ===")
        logger.info(f"User: {user_email}")
        
        self.user_email = user_email
        self.knowledge_base = KnowledgeBase(user_email)
        
        # Set credentials for calendar tools
        if credentials:
            set_credentials(credentials)
            logger.info("Calendar credentials configured")
        
        # Build additional context from knowledge base
        kb_content = self.knowledge_base.get_knowledge_base()
        
        additional_context = dedent(f"""
            Current date/time: {datetime.now(pytz.timezone(TIMEZONE)).strftime('%A, %B %d, %Y at %I:%M %p')}
            Timezone: {TIMEZONE}
            
            User's Knowledge Base:
            {kb_content if kb_content else "No knowledge base entries yet."}
        """)
        
        # Create the Agno agent
        self.agent = Agent(
            name="Auto Assistant",
            model=get_llm_model(),
            tools=[
                get_todays_events,
                get_upcoming_events,
                find_free_time_slots,
                create_calendar_event,
                create_birthday_reminder,
                schedule_interview,
                delete_calendar_event,
                send_email,
            ],
            instructions=ASSISTANT_INSTRUCTIONS,
            additional_context=additional_context,
            markdown=True,
            debug_mode=True,  # Enable Agno debug logging
            add_datetime_to_context=True,
            tool_call_limit=MAX_TOOL_CALLS,
            # Memory - keep conversation history
            add_history_to_context=True,
            num_history_runs=NUM_HISTORY_RUNS,
            db=team_storage,
        )
        
        logger.info(f"Agno agent initialized with {len(self.agent.tools)} tools")
    
    def update_credentials(self, credentials):
        """Update the calendar credentials."""
        set_credentials(credentials)
        logger.info("Calendar credentials updated")
    
    def chat(self, user_message: str, calendar_context: str = "") -> str:
        """Process a chat message and return a response."""
        logger.info(f"=== CHAT REQUEST ===")
        logger.info(f"User message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
        
        try:
            # Run the agent synchronously
            response = self.agent.run(user_message)
            
            result = response.content if response.content else "I couldn't generate a response."
            logger.info(f"Chat response generated ({len(result)} chars)")
            
            return result
            
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return f"I encountered an error: {str(e)}"
    
    async def achat(self, user_message: str) -> str:
        """Process a chat message asynchronously."""
        logger.info(f"=== ASYNC CHAT REQUEST ===")
        logger.info(f"User message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
        
        try:
            response = await self.agent.arun(user_message)
            
            result = response.content if response.content else "I couldn't generate a response."
            logger.info(f"Async chat response generated ({len(result)} chars)")
            
            return result
            
        except Exception as e:
            logger.error(f"Async chat failed: {e}")
            return f"I encountered an error: {str(e)}"
    
    def generate_daily_brief(self, calendar_events=None) -> str:
        """Generate a daily brief."""
        logger.info("=== GENERATING DAILY BRIEF ===")
        
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz)
        
        prompt = dedent(f"""
            Generate a concise, friendly daily brief for {today.strftime('%A, %B %d, %Y')}.
            
            First, check my calendar for today's events using the get_todays_events tool.
            
            Then create a brief that:
            1. Starts with an appropriate greeting for the time of day
            2. Summarizes today's calendar events
            3. Mentions any important reminders from my knowledge base
            4. Notes any upcoming birthdays or important dates
            5. Ends with a helpful or motivational note
            
            Keep it concise but personal.
        """)
        
        return self.chat(prompt)
    
    def analyze_calendar(self, days: int = 7) -> str:
        """Analyze the calendar and provide suggestions."""
        logger.info(f"=== ANALYZING CALENDAR ({days} days) ===")
        
        prompt = dedent(f"""
            Analyze my calendar for the next {days} days and provide insights.
            
            First, get my upcoming events using the get_upcoming_events tool.
            
            Then analyze and tell me:
            1. Any potential scheduling conflicts or overly busy days
            2. Important dates that might be missing (based on my knowledge base)
            3. Suggestions for time blocking or better organization
            4. Any gaps that could be used for focused work or self-care
            
            Be specific and actionable with your suggestions.
        """)
        
        return self.chat(prompt)
    
    def clear_conversation(self):
        """Clear the conversation history."""
        logger.info("Clearing conversation history")
        # Create a new agent instance to reset history
        self.agent = Agent(
            name="Auto Assistant",
            model=get_llm_model(),
            tools=[
                get_todays_events,
                get_upcoming_events,
                find_free_time_slots,
                create_calendar_event,
                create_birthday_reminder,
                schedule_interview,
                delete_calendar_event,
                send_email,
            ],
            instructions=ASSISTANT_INSTRUCTIONS,
            markdown=True,
            debug_mode=True,
            add_datetime_to_context=True,
            tool_call_limit=MAX_TOOL_CALLS,
            add_history_to_context=True,
            num_history_runs=NUM_HISTORY_RUNS,
        )


# Convenience function for CLI usage
async def main():
    """CLI interface for testing the assistant."""
    print("🦾 Auto Assistant CLI")
    print("Type 'exit' to quit.\n")
    
    assistant = AIAssistant(user_email="test@example.com")
    
    while True:
        user_input = input("💁‍♀️ You: ")
        if user_input.strip().lower() == "exit":
            break
        
        response = await assistant.achat(user_input)
        print(f"🤖 Auto: {response}\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
