"""AI Assistant using Agno framework."""
from textwrap import dedent
from typing import Optional
from datetime import datetime
import pytz
from agno.db.postgres import PostgresDb
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.learn.machine import LearningMachine
from agno.learn.config import (
    LearningMode,
    UserProfileConfig,
    SessionContextConfig,
    EntityMemoryConfig,
)
from src.config import (
    LLM_PROVIDER,
    LLM_MODEL,
    TIMEZONE,
)
from src.database import DATABASE_URL, init_db
from src.knowledge_base import KnowledgeBase
from src.logging_utils import get_logger
from src.tools import (
    set_credentials,
    set_knowledge_base,
    set_assistant,
    get_todays_events,
    get_upcoming_events,
    find_free_time_slots,
    create_calendar_event,
    create_birthday_reminder,
    schedule_interview,
    delete_calendar_event,
    send_email,
    get_reminders,
    add_reminder,
    remove_reminder,
    get_crucial_events,
    add_crucial_event,
    remove_crucial_event,
    generate_daily_brief,
    get_grocery_list,
    add_to_grocery_list,
    remove_from_grocery_list,
    clear_weekly_grocery_items,
    get_todo_list,
    add_todo_item,
    remove_todo_item,
    clear_todo_items,
)

logger = get_logger(__name__)

# Agent configuration
MAX_TOOL_CALLS = 25
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
init_db()

team_storage = PostgresDb(
    db_url=DATABASE_URL
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
    - Manage a grocery list with recurring staples and one-time items
    - Manage a todo list with personal and work items

    IMPORTANT GUIDELINES:

    1. **Learning and Memory**:
       - Automatically remember important information about the user without being asked
       - Track preferences, important people, relationships, and events
       - Build a rich understanding of the user's life and context over time
       - You have learning capabilities that automatically store this information

    2. **Before creating events**: Always confirm the details with the user first.
       - Ask for missing information (date, time, duration)
       - Clarify ambiguous requests

    3. **Date/Time handling**:
       - When the user says "tomorrow", "next Monday", etc., calculate the actual date
       - Use 24-hour format (HH:MM) for the tools
       - Default duration is 60 minutes unless specified

    4. **Be helpful and proactive**:
       - If the user's calendar looks busy, mention it
       - Suggest optimal times based on their schedule
       - Remind them of potential conflicts
       - Use remembered information to personalize responses

    5. **Knowledge Base**:
       - Reference the user's knowledge base for context about important people, preferences
       - Your learned memories complement the knowledge base
       - Use this context to personalize your responses

    6. **Response format**:
       - Be concise but friendly
       - Use emojis sparingly for visual clarity
       - When showing calendar info, format it nicely
""")


class AIAssistant:
    """Agno-powered AI Assistant for calendar and task management."""
    
    def __init__(self, user_email: str, credentials=None, session_id: Optional[str] = None):
        """Initialize the assistant for a user."""
        logger.info(f"=== INITIALIZING AGNO ASSISTANT ===")
        logger.info(f"User: {user_email}")

        self.user_email = user_email
        self.session_id = session_id or datetime.now().strftime("%Y%m%d")
        self.knowledge_base = KnowledgeBase(user_email)
        
        # Set credentials for calendar tools
        if credentials:
            set_credentials(credentials)
            logger.info("Calendar credentials configured")

        # Set knowledge base for reminder tools
        set_knowledge_base(self.knowledge_base)
        
        # Build additional context from knowledge base
        kb_content = self.knowledge_base.get_knowledge_base()
        
        self.additional_context = dedent(f"""
            Current date/time: {datetime.now(pytz.timezone(TIMEZONE)).strftime('%A, %B %d, %Y at %I:%M %p')}
            Timezone: {TIMEZONE}
            
            User's Knowledge Base:
            {kb_content if kb_content else "No knowledge base entries yet."}
        """)
        
        # Get the model for learning
        model = get_llm_model()

        # Create the Agno agent with learning
        self.agent = Agent(
            name="Auto Assistant",
            model=model,
            tools=[
                get_todays_events,
                get_upcoming_events,
                find_free_time_slots,
                create_calendar_event,
                create_birthday_reminder,
                schedule_interview,
                delete_calendar_event,
                send_email,
                get_reminders,
                add_reminder,
                remove_reminder,
                get_crucial_events,
                add_crucial_event,
                remove_crucial_event,
                generate_daily_brief,
                get_grocery_list,
                add_to_grocery_list,
                remove_from_grocery_list,
                clear_weekly_grocery_items,
                get_todo_list,
                add_todo_item,
                remove_todo_item,
                clear_todo_items,
            ],
            instructions=ASSISTANT_INSTRUCTIONS,
            additional_context=self.additional_context,
            markdown=True,
            debug_mode=True,  # Enable Agno debug logging
            add_datetime_to_context=True,
            tool_call_limit=MAX_TOOL_CALLS,
            # Memory - keep conversation history
            add_history_to_context=True,
            num_history_runs=NUM_HISTORY_RUNS,
            db=team_storage,
            # Learning capabilities
            learning=LearningMachine(
                db=team_storage,
                model=model,
                namespace=f"user:{self.user_email}:personal",
                user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
                session_context=SessionContextConfig(enable_planning=True),
                entity_memory=EntityMemoryConfig(
                    mode=LearningMode.AGENTIC,
                ),
            ),
            user_id=self.user_email,
            session_id=self.session_id,
        )

        logger.info(f"Agno agent initialized with {len(self.agent.tools)} tools")

        # Set assistant reference for daily brief tool
        set_assistant(self)

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
    
    def generate_daily_brief(self) -> str:
        """Generate a concise daily brief with random reminders and only big calendar items."""
        logger.info("=== GENERATING DAILY BRIEF ===")
        
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz)
        
        # Pick one random personal and one random professional reminder
        personal_reminder, professional_reminder = self.knowledge_base.get_random_daily_reminders()
        
        # Crucial events for context (birthdays, anniversaries, etc.)
        crucial_events = self.knowledge_base.get_crucial_events()
        crucial_section = ""
        if crucial_events:
            crucial_section = "CRUCIAL EVENTS TO WATCH FOR (from user's list):\n" + "\n".join(
                f"- {e['name']}: {e['date']}" for e in crucial_events
            ) + "\n\n"
        
        reminders_section = ""
        if personal_reminder or professional_reminder:
            reminders_section = "INCLUDE THESE REMINDERS in the correct sections:\n"
            if professional_reminder:
                reminders_section += f"- Work (💻): {professional_reminder}\n"
            if personal_reminder:
                reminders_section += f"- Personal (💁‍♀️): {personal_reminder}\n"
        
        prompt = dedent(f"""
            Generate a daily brief for {today.strftime('%A, %B %d, %Y')}.
            
            Use get_todays_events and get_upcoming_events(days=30) to check my calendar.
            
            {crucial_section}
            CRITICAL - ONLY mention these calendar items (skip the rest):
            - Big personal dates: Today is X's birthday, Today is our anniversary, Valentine's Day is Saturday
            - Important work events: Team offsite in 3 weeks (add note if relevant - e.g. "don't forget to let Kennedy know")
            - Milestone events: first day of X, important deadlines
            DO NOT list routine meetings or "no birthdays coming up" or redundant summaries.
            If nothing big is happening, skip the Calendar section or say "Nothing major coming up."
            
            {reminders_section}
            
            OUTPUT FORMAT - use exactly this structure (omit a section if empty):

            <insert short greeting here>
            
            📆 Calendar \n
            <one line: big calendar items only, or "Nothing major coming up.">
            
            💻 Work \n
            <one line: the work reminder if provided>
            
            💁‍♀️ Personal \n
            <one line: the personal reminder if provided>
            
            Keep each section to one short line. But they should be separate lines.
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

        model = get_llm_model()

        self.agent = Agent(
            name="Auto Assistant",
            model=model,
            tools=[
                get_todays_events,
                get_upcoming_events,
                find_free_time_slots,
                create_calendar_event,
                create_birthday_reminder,
                schedule_interview,
                delete_calendar_event,
                send_email,
                get_reminders,
                add_reminder,
                remove_reminder,
                get_crucial_events,
                add_crucial_event,
                remove_crucial_event,
                generate_daily_brief,
                get_grocery_list,
                add_to_grocery_list,
                remove_from_grocery_list,
                clear_weekly_grocery_items,
                get_todo_list,
                add_todo_item,
                remove_todo_item,
                clear_todo_items,
            ],
            instructions=ASSISTANT_INSTRUCTIONS,
            additional_context=self.additional_context,
            markdown=True,
            debug_mode=True,  # Enable Agno debug logging
            add_datetime_to_context=True,
            tool_call_limit=MAX_TOOL_CALLS,
            # Memory - keep conversation history
            add_history_to_context=True,
            num_history_runs=NUM_HISTORY_RUNS,
            db=team_storage,
            # Learning capabilities
            learning=LearningMachine(
                db=team_storage,
                model=model,
                namespace=f"user:{self.user_email}:personal",
                user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
                session_context=SessionContextConfig(enable_planning=True),
                entity_memory=EntityMemoryConfig(
                    mode=LearningMode.AGENTIC,
                ),
            ),
            user_id=self.user_email,
            session_id=self.session_id,
        )

    def get_learned_memories(self) -> dict:
        """Get all learned memories from Agno's learning system."""
        logger.info("=== RETRIEVING LEARNED MEMORIES ===")

        try:
            memories = {
                "user_profile": [],
                "entities": [],
                "session_context": [],
            }

            # Debug: Log all agent attributes related to learning
            logger.info("=== AGENT LEARNING ATTRIBUTES ===")
            logger.info(f"Has learning: {hasattr(self.agent, 'learning')}")
            logger.info(f"Learning value: {getattr(self.agent, 'learning', None)}")
            logger.info(f"Has user_profile: {hasattr(self.agent, 'user_profile')}")
            logger.info(f"User profile value: {getattr(self.agent, 'user_profile', None)}")
            logger.info(f"Has entity_memory: {hasattr(self.agent, 'entity_memory')}")
            logger.info(f"Entity memory value: {getattr(self.agent, 'entity_memory', None)}")
            logger.info(f"Has user_profile_store: {hasattr(self.agent, 'user_profile_store')}")
            logger.info(f"User profile store: {getattr(self.agent, 'user_profile_store', None)}")
            logger.info(f"Has entity_memory_store: {hasattr(self.agent, 'entity_memory_store')}")
            logger.info(f"Entity memory store: {getattr(self.agent, 'entity_memory_store', None)}")

            # Access stores through the learning machine
            if hasattr(self.agent, 'learning') and self.agent.learning:
                learning = self.agent.learning
                logger.info(f"Learning object: {learning}")

                # Try to access stores from learning machine
                if hasattr(learning, 'user_profile_store'):
                    logger.info(f"user_profile_store from learning: {learning.user_profile_store}")
                    try:
                        store = learning.user_profile_store
                        if store and hasattr(store, 'get'):
                            stored_profile = store.get(user_id=self.user_email)
                            logger.info(f"Retrieved user profile: {stored_profile}")
                            if stored_profile:
                                if hasattr(stored_profile, 'to_dict'):
                                    memories["user_profile"].append(stored_profile.to_dict())
                                elif hasattr(stored_profile, '__dict__'):
                                    memories["user_profile"].append(vars(stored_profile))
                                else:
                                    memories["user_profile"].append({"data": str(stored_profile)})
                    except Exception as e:
                        logger.warning(f"Error getting user profile from store: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())

                if hasattr(learning, 'entity_memory_store'):
                    logger.info(f"entity_memory_store from learning: {learning.entity_memory_store}")
                    try:
                        store = learning.entity_memory_store
                        if store and hasattr(store, 'search'):
                            # Use search with empty query to get all entities
                            # Don't pass namespace - it uses the LearningMachine's namespace
                            stored_entities = store.search(
                                query="",
                                user_id=self.user_email,
                                limit=100
                            )
                            logger.info(f"Retrieved {len(stored_entities) if stored_entities else 0} entities")
                            if stored_entities:
                                for entity in stored_entities:
                                    logger.info(f"Entity: {entity}")
                                    if hasattr(entity, 'to_dict'):
                                        memories["entities"].append(entity.to_dict())
                                    elif hasattr(entity, '__dict__'):
                                        memories["entities"].append(vars(entity))
                                    else:
                                        memories["entities"].append({"data": str(entity)})
                    except Exception as e:
                        logger.warning(f"Error searching entities from store: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())

                if hasattr(learning, 'session_context_store'):
                    logger.info(f"session_context_store from learning: {learning.session_context_store}")
                    try:
                        store = learning.session_context_store
                        if store and hasattr(store, 'get'):
                            # SessionContextStore.get() only takes session_id
                            stored_context = store.get(session_id=self.session_id)
                            logger.info(f"Retrieved session context: {stored_context}")
                            if stored_context:
                                if hasattr(stored_context, 'to_dict'):
                                    memories["session_context"].append(stored_context.to_dict())
                                elif hasattr(stored_context, '__dict__'):
                                    memories["session_context"].append(vars(stored_context))
                                else:
                                    memories["session_context"].append({"data": str(stored_context)})
                    except Exception as e:
                        logger.warning(f"Error getting session context from store: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())

            logger.info(f"Retrieved {len(memories['user_profile'])} user profile memories and {len(memories['entities'])} entity memories")
            return memories

        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"user_profile": [], "entities": [], "session_context": []}


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
