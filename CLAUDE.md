# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a personal AI assistant with a Streamlit frontend that integrates with Google Calendar using OAuth. The assistant uses the Agno AI framework with either Anthropic Claude or OpenAI models to provide calendar management, knowledge base functionality, and daily briefs.

## Development Commands

### Running the Application
```bash
# Install dependencies
uv sync

# Run the Streamlit app (main interface)
uv run streamlit run app.py

# Run the CLI assistant (for testing)
uv run python -m src.assistant

# Run the background scheduler (for automated daily briefs)
uv run python -m src.scheduler
```

### Environment Setup
- Copy `.env.example` to `.env` and configure:
  - Google OAuth credentials (Client ID, Client Secret, Redirect URI)
  - LLM provider (`anthropic` or `openai`) and API keys
  - PostgreSQL database credentials (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB)
  - Timezone (default: America/Toronto)

## Architecture

### Core Components

**Agno Framework Integration**
- The assistant is built using the Agno AI framework (`agno>=1.0.0`)
- Uses `Agent` class from `agno.agent` with conversation history and PostgreSQL storage
- All calendar operations are implemented as Agno `@tool` decorated functions in `src/tools.py`
- The agent stores conversation history in PostgreSQL using `agno.db.postgres.PostgresDb`

**LLM Provider Abstraction**
- The system supports both Anthropic (Claude) and OpenAI models
- Provider selection is controlled via `LLM_PROVIDER` environment variable in `src/config.py`
- `get_llm_model()` function in `src/assistant.py` returns the appropriate model:
  - Anthropic: `Claude(id=LLM_MODEL)` from `agno.models.anthropic`
  - OpenAI: `OpenAIChat(id=LLM_MODEL)` from `agno.models.openai`
- Default model: `claude-sonnet-4-20250514`

**Google Calendar Integration**
- OAuth flow handled by `src/integrations/google_auth.py` and `src/google_auth.py`
- Calendar operations in `src/integrations/calendar.py` and `src/calendar_service.py`
- Credentials stored module-level in `src/tools.py` via `set_credentials()` function
- All calendar tools (`get_todays_events`, `create_calendar_event`, etc.) use `_get_calendar_service()` which builds the Google Calendar API client using stored credentials

**Assistant Architecture**
- `AIAssistant` class in `src/assistant.py` is the core orchestrator
- On initialization:
  - Loads user's knowledge base from `data/users/{email}/knowledge_base.md`
  - Creates an Agno `Agent` with calendar tools, instructions, and context
  - Sets up PostgreSQL storage for conversation history
- The agent maintains conversation history across sessions (configurable via `NUM_HISTORY_RUNS`)
- `chat()` method processes messages synchronously, `achat()` for async
- Agent has a `MAX_TOOL_CALLS = 5` limit to prevent infinite loops

**Knowledge Base System**
- Markdown-based per-user storage in `data/users/{email}/`
- `KnowledgeBase` class in `src/knowledge_base.py` manages user memories
- Files stored: `knowledge_base.md` (markdown), `reminders.json` (structured data)
- Supports sections: About Me, Important People, Work Context, Preferences, Custom Reminders
- Content is injected into agent's `additional_context` parameter on initialization

### Streamlit UI (`app.py`)

**Pages**
- Chat interface with the assistant ("🦾 Auto")
- Knowledge base editor ("🧠 Knowledge Base")
- Daily brief auto-generation ("📊 Daily Brief")

**Session State Management**
- `st.session_state.assistant` - AIAssistant instance (initialized once per user)
- `st.session_state.knowledge_base` - KnowledgeBase instance
- `st.session_state.messages` - Chat history for UI display
- `st.session_state.google_credentials` - OAuth tokens
- Assistant credentials are updated when credentials change via `update_credentials()`

**Authentication Flow**
1. User clicks "Sign in with Google" → redirects to Google OAuth
2. Google redirects back to `http://localhost:8501` with auth code
3. `check_authentication()` in `src/integrations/google_auth.py` exchanges code for tokens
4. Tokens stored in session state and used to initialize calendar service

### Database Storage
- PostgreSQL database required for Agno conversation history
- Connection string format: `postgresql+psycopg://{user}:{password}@{host}/{db}`
- Database URL built in `src/assistant.py` from environment variables
- `PostgresDb` handles table creation and storage automatically

## Key Files

- `app.py` - Streamlit application entry point
- `src/assistant.py` - AIAssistant class using Agno framework
- `src/tools.py` - Agno tool definitions for calendar operations
- `src/config.py` - Configuration and environment variables
- `src/knowledge_base.py` - Knowledge base management
- `src/integrations/google_auth.py` - OAuth flow and token management
- `src/integrations/calendar.py` - Google Calendar API wrappers
- `pyproject.toml` - Dependencies managed with `uv`

## Important Implementation Details

**Calendar Tool Pattern**
- All tools are decorated with `@tool` from `agno.tools`
- Tools must include docstrings with "WHEN TO USE", "ARGS", and "RETURNS" sections
- Module-level `_credentials` variable stores Google credentials
- Always call `set_credentials()` before using tools
- Tools use `_get_calendar_service()` helper to build the Google Calendar client

**Agent Lifecycle**
- Agent is created per user session with their knowledge base context
- Conversation history persists across page navigations via PostgreSQL
- To clear conversation: call `clear_conversation()` which creates a new agent instance
- Agent instructions are in `ASSISTANT_INSTRUCTIONS` constant in `src/assistant.py`

**Date/Time Handling**
- All dates use timezone-aware `datetime` with `pytz.timezone(TIMEZONE)`
- Calendar tools expect dates in `YYYY-MM-DD` format
- Times in 24-hour `HH:MM` format
- Google Calendar API uses ISO format with timezone info

**Error Handling**
- Tools catch exceptions and return error messages as strings
- Logging via `src/logging_utils.py` - use `get_logger(__name__)`
- Streamlit shows errors via `st.error()` in UI

## Slack Integration (Optional)

The codebase has optional Slack integration configuration in `.env.example`:
- `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` for `/ea` slash commands
- FastAPI server on port 8000 for webhook handling (not currently implemented in main app)

## Data Storage

```
data/
├── users/
│   └── {email_sanitized}/
│       ├── knowledge_base.md
│       ├── knowledge_base_backup_*.md
│       └── reminders.json
└── tokens/  # OAuth tokens (handled by google_auth)
```

## PostgreSQL Database

The assistant requires PostgreSQL for conversation history storage:
- Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DB` in `.env`
- Agno automatically creates required tables on first run
- Conversation history persists across app restarts
