# 🤖 AI Assistant

A personal AI assistant with a Streamlit frontend that helps you manage your calendar, maintain a knowledge base, and stay organized with daily reminders.

## Features

### 📅 Calendar Management
- **View Events**: See your upcoming Google Calendar events
- **Add Events**: Create new calendar events with natural language
- **Recurring Birthdays**: Add yearly birthday reminders that repeat automatically
- **Interview Scheduling**: Book interviews with multiple attendees and find available time slots

### 🧠 Knowledge Base
- **Personal Memory**: Store information about yourself, important people, work context, and preferences
- **Markdown-based**: Edit your knowledge base in a simple markdown format
- **Contextual Responses**: The AI uses your knowledge base to provide personalized responses

### ⏰ Daily Briefs & Reminders
- **Morning Brief**: Get a personalized daily summary of your calendar and reminders
- **Calendar Analysis**: AI reviews your schedule and suggests what might be missing
- **Custom Reminders**: Add daily, recurring, or one-time reminders

### 💬 AI Chat
- **Natural Language**: Chat naturally with your assistant
- **Context-Aware**: Responses consider your calendar and knowledge base
- **Smart Updates**: Automatically update your knowledge base from conversation

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/ai-assistant.git
cd ai-assistant

# Install dependencies with uv
uv sync
```

### 2. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit with your credentials
nano .env  # or open in your editor
```

### 3. Set Up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the **Google Calendar API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Select **Web application** as the application type
6. Add `http://localhost:8501` to **Authorized redirect URIs**
7. Copy the **Client ID** and **Client Secret** to your `.env` file

### 4. Set Up LLM API

Choose either Anthropic or OpenAI:

**Anthropic (Claude):**
1. Get an API key from [console.anthropic.com](https://console.anthropic.com)
2. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. Set `LLM_PROVIDER=anthropic`

**OpenAI (GPT):**
1. Get an API key from [platform.openai.com](https://platform.openai.com)
2. Add to `.env`: `OPENAI_API_KEY=sk-...`
3. Set `LLM_PROVIDER=openai`

### 5. Run the App

```bash
uv run streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Usage

### First Time Setup

1. Click **Sign in with Google** to authenticate
2. Grant calendar permissions when prompted
3. You'll be redirected back to the app

### Chat with Assistant

Use natural language to:
- "What's on my calendar today?"
- "Add Mom's birthday on March 15th every year"
- "Schedule an interview with John for tomorrow at 2pm with alice@company.com and bob@company.com"
- "Remember that my partner is allergic to shellfish"
- "What am I missing this week?"

### Manage Knowledge Base

1. Go to **🧠 Knowledge Base**
2. Edit the markdown content to add:
   - Information about yourself
   - Important people and their details
   - Work context
   - Preferences
   - Custom reminders

### Get Daily Brief

1. Go to **📊 Daily Brief**
2. Click **Generate Today's Brief** for a personalized summary
3. Click **Analyze My Calendar** for suggestions on what might be missing

## Project Structure

```
ai-assistant/
├── app.py                  # Main Streamlit application
├── pyproject.toml         # Python dependencies (uv)
├── uv.lock                # Locked dependencies
├── .env.example           # Example environment variables
├── data/                  # User data storage
│   ├── users/            # Per-user knowledge bases
│   └── tokens/           # OAuth tokens
└── src/
    ├── __init__.py
    ├── config.py          # Configuration management
    ├── assistant.py       # AI assistant core logic
    ├── knowledge_base.py  # Knowledge base management
    ├── scheduler.py       # Background scheduler for reminders
    └── integrations/
        ├── __init__.py
        ├── google_auth.py # Google OAuth handling
        └── calendar.py    # Google Calendar integration
```

## Background Scheduler (Optional)

To run daily briefs automatically:

```bash
# Set the time for daily briefs
export BRIEF_HOUR=7
export BRIEF_MINUTE=0

# Run the scheduler
uv run python -m src.scheduler
```

Or add to your crontab:
```cron
0 7 * * * cd /path/to/ai-assistant && uv run python -m src.scheduler
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | Yes |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI (default: http://localhost:8501) | No |
| `LLM_PROVIDER` | "anthropic" or "openai" | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key | If using Anthropic |
| `OPENAI_API_KEY` | OpenAI API key | If using OpenAI |
| `LLM_MODEL` | Model name | No (has defaults) |
| `TIMEZONE` | Your timezone (default: America/Toronto) | No |
| `BRIEF_HOUR` | Hour for daily brief (0-23) | No |
| `BRIEF_MINUTE` | Minute for daily brief (0-59) | No |

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Streamlit Cloud

1. Push your code to GitHub
2. Connect to [Streamlit Cloud](https://streamlit.io/cloud)
3. Add your environment variables as secrets
4. Deploy!

**Note:** For production, update `GOOGLE_REDIRECT_URI` to your deployed URL.

## Security Notes

- OAuth tokens are stored locally in `data/tokens/`
- API keys should be kept in `.env` (not committed to git)
- The `.env` file is in `.gitignore` by default
- For production, use proper secrets management

## License

MIT
