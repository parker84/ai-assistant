"""AI Assistant core logic with LLM integration."""
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pytz

from src.config import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    LLM_PROVIDER,
    LLM_MODEL,
    TIMEZONE,
)
from src.knowledge_base import KnowledgeBase


class AIAssistant:
    """Main AI Assistant class that orchestrates all functionality."""
    
    SYSTEM_PROMPT = """You are a helpful personal AI assistant. You help the user manage their calendar, 
remember important things, and stay organized.

You have access to:
1. The user's Google Calendar - you can view events and help add new ones
2. The user's Knowledge Base - personal information, preferences, and custom reminders
3. The ability to set reminders and provide daily briefs

When helping with calendar tasks:
- Be specific about dates and times
- Confirm details before creating events
- Suggest optimal times when scheduling meetings

When generating daily briefs:
- Summarize today's calendar events
- Include relevant reminders from the knowledge base
- Be concise but comprehensive
- Use a friendly, personal tone

When the user wants to add something to their knowledge base:
- Help them organize the information
- Suggest which section it belongs in
- Confirm the addition

Always be helpful, proactive, and personable. Remember context from the conversation."""

    def __init__(self, user_email: str):
        """Initialize the assistant for a user."""
        self.user_email = user_email
        self.knowledge_base = KnowledgeBase(user_email)
        self.conversation_history: List[Dict[str, str]] = []
        
        # Initialize LLM client
        if LLM_PROVIDER == "anthropic":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                self.provider = "anthropic"
            except ImportError:
                self.client = None
                self.provider = None
        elif LLM_PROVIDER == "openai":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                self.provider = "openai"
            except ImportError:
                self.client = None
                self.provider = None
        else:
            self.client = None
            self.provider = None
    
    def _call_llm(self, messages: List[Dict[str, str]], system: str = None) -> str:
        """Call the LLM with the given messages."""
        if not self.client:
            return "LLM not configured. Please set up your API keys in the .env file."
        
        system_prompt = system or self.SYSTEM_PROMPT
        
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=LLM_MODEL,
                    system=system_prompt,
                    messages=messages,
                )
                return response.content[0].text
            
            elif self.provider == "openai":
                full_messages = [{"role": "system", "content": system_prompt}] + messages
                response = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=full_messages,
                )
                return response.choices[0].message.content
            
        except Exception as e:
            return f"Error calling LLM: {str(e)}"
    
    def chat(self, user_message: str, calendar_context: str = "") -> str:
        """Process a chat message and return a response."""
        # Build context
        kb_context = self.knowledge_base.get_knowledge_base()
        
        context = f"""
Current date/time: {datetime.now(pytz.timezone(TIMEZONE)).strftime('%A, %B %d, %Y at %I:%M %p')}

User's Knowledge Base:
{kb_context}

{f"User's Calendar Context:{chr(10)}{calendar_context}" if calendar_context else ""}
"""
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Build messages with context
        messages = [
            {"role": "user", "content": f"Context:\n{context}"},
            {"role": "assistant", "content": "I understand the context. I'm ready to help."},
        ] + self.conversation_history
        
        # Get response
        response = self._call_llm(messages)
        
        # Add to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response
    
    def generate_daily_brief(self, calendar_events: List[Dict[str, Any]]) -> str:
        """Generate a daily brief based on calendar and knowledge base."""
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz)
        
        # Format calendar events
        events_text = ""
        if calendar_events:
            events_text = "Today's Calendar Events:\n"
            for event in calendar_events:
                start = event.get("start", {})
                if "dateTime" in start:
                    event_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                    time_str = event_time.strftime("%I:%M %p")
                else:
                    time_str = "All day"
                
                summary = event.get("summary", "No title")
                events_text += f"- {time_str}: {summary}\n"
        else:
            events_text = "No calendar events today.\n"
        
        # Get knowledge base context
        kb_context = self.knowledge_base.get_daily_brief_context()
        
        prompt = f"""Generate a concise, friendly daily brief for {today.strftime('%A, %B %d, %Y')}.

{events_text}

Knowledge Base and Reminders:
{kb_context}

Instructions:
1. Start with a brief greeting appropriate for the time of day
2. Summarize today's calendar events
3. Include any relevant reminders from the knowledge base
4. Mention any birthdays, anniversaries, or important dates coming up
5. End with a motivational or helpful note
6. Keep it concise but personal

Generate the daily brief:"""

        messages = [{"role": "user", "content": prompt}]
        return self._call_llm(messages)
    
    def analyze_calendar(self, events: List[Dict[str, Any]], days: int = 7) -> str:
        """Analyze calendar and provide suggestions for what might be missing."""
        kb_context = self.knowledge_base.get_knowledge_base()
        
        # Format events
        events_text = ""
        for event in events:
            start = event.get("start", {})
            if "dateTime" in start:
                event_date = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                date_str = event_date.strftime("%B %d at %I:%M %p")
            else:
                date_str = start.get("date", "Unknown date")
            
            summary = event.get("summary", "No title")
            events_text += f"- {date_str}: {summary}\n"
        
        prompt = f"""Analyze this calendar for the next {days} days and suggest what might be missing or could be improved.

Calendar Events:
{events_text if events_text else "No events scheduled"}

User's Knowledge Base (context about their life, important people, work):
{kb_context}

Based on the knowledge base and calendar, please:
1. Identify any important dates/events that might be missing (birthdays, anniversaries, etc.)
2. Suggest any recurring events that should be scheduled
3. Point out any potential scheduling conflicts or overly busy days
4. Recommend time blocks for important activities mentioned in the knowledge base
5. Highlight anything that seems like it might be forgotten

Be specific and actionable in your suggestions."""

        messages = [{"role": "user", "content": prompt}]
        return self._call_llm(messages)
    
    def parse_calendar_request(self, request: str, calendar_context: str = "") -> Dict[str, Any]:
        """Parse a natural language calendar request into structured data."""
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz)
        
        prompt = f"""Parse this calendar request and extract the relevant information.

Current date/time: {today.strftime('%A, %B %d, %Y at %I:%M %p')}

User's request: "{request}"

{f"Current calendar context:{chr(10)}{calendar_context}" if calendar_context else ""}

Extract the following information (if present) and return as JSON:
{{
    "action": "create" | "update" | "delete" | "query",
    "event_type": "meeting" | "birthday" | "interview" | "reminder" | "other",
    "summary": "event title",
    "date": "YYYY-MM-DD",
    "time": "HH:MM" (24-hour format),
    "duration_minutes": number,
    "is_recurring": boolean,
    "recurrence_type": "daily" | "weekly" | "monthly" | "yearly" | null,
    "attendees": ["email1", "email2"] or null,
    "location": "location" or null,
    "description": "description" or null,
    "needs_clarification": boolean,
    "clarification_question": "question to ask user" or null
}}

Return ONLY the JSON, no other text."""

        messages = [{"role": "user", "content": prompt}]
        response = self._call_llm(messages)
        
        # Try to parse JSON from response
        try:
            import json
            # Clean up response - find JSON in the response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except Exception as e:
            return {
                "action": "query",
                "needs_clarification": True,
                "clarification_question": f"I couldn't understand that request. Could you please rephrase? Error: {str(e)}",
            }
    
    def update_knowledge_from_chat(self, user_message: str) -> Optional[str]:
        """Determine if a message should update the knowledge base and extract the update."""
        prompt = f"""Analyze this message and determine if the user wants to add or update their knowledge base/memory.

User's message: "{user_message}"

If the user wants to remember something or update their profile/preferences, extract:
1. What section it belongs to (About Me, Important People, Work Context, Preferences, Custom Reminders, Notes)
2. The information to add

Return as JSON:
{{
    "should_update": boolean,
    "section": "section name" or null,
    "content": "formatted content to add" or null,
    "response": "confirmation message to user"
}}

Return ONLY the JSON, no other text."""

        messages = [{"role": "user", "content": prompt}]
        response = self._call_llm(messages)
        
        try:
            import json
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            result = json.loads(response)
            
            if result.get("should_update") and result.get("section") and result.get("content"):
                success = self.knowledge_base.append_to_knowledge_base(
                    result["section"],
                    result["content"]
                )
                if success:
                    return result.get("response", "I've added that to your knowledge base.")
            
            return None
        except Exception:
            return None
    
    def clear_conversation(self):
        """Clear the conversation history."""
        self.conversation_history = []
