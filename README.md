# AI Assistant

A personal AI assistant with a Streamlit frontend that helps you manage your calendar, maintain a knowledge base, and stay organized with daily reminders.

## Features

- **Calendar Management** -- View, create, and manage Google Calendar events via natural language
- **Knowledge Base** -- Markdown-based personal memory the AI uses for context
- **Daily Briefs & Reminders** -- Automated morning summaries with calendar highlights and custom reminders
- **AI Chat** -- Context-aware conversation using your calendar and knowledge base

## Local Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- A Google Cloud project with the Calendar API enabled and OAuth 2.0 credentials

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID from [Google Cloud Console](https://console.cloud.google.com) |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 Client Secret |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8501` for local dev |
| `LLM_PROVIDER` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | API key from [console.anthropic.com](https://console.anthropic.com) (if using Anthropic) |
| `OPENAI_API_KEY` | API key from [platform.openai.com](https://platform.openai.com) (if using OpenAI) |
| `POSTGRES_USER` | Postgres username (default: `assistant`) |
| `POSTGRES_PASSWORD` | Postgres password (default: `assistant`) |
| `POSTGRES_HOST` | `postgres` when using Docker Compose, `localhost` when running outside Docker |
| `POSTGRES_DB` | Postgres database name (default: `assistant`) |

The remaining variables (`TIMEZONE`, `LLM_MODEL`, `GMAIL_*`, `BRIEF_*`, `USER_EMAIL`) have sensible defaults -- see `.env.example` for details.

### 2a. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

This starts three services:

- **app** -- Streamlit UI at `http://localhost:8501`
- **scheduler** -- Background job that emails a daily brief
- **postgres** -- PostgreSQL 16 database

To run just the app without the scheduler:

```bash
docker compose up --build app postgres
```

### 2b. Run without Docker

If you prefer to use your own Postgres instance:

```bash
# Set POSTGRES_HOST=localhost (or your DB host) in .env
uv sync

# Run the Streamlit app
uv run streamlit run app.py

# (Optional) Run the scheduler in a separate terminal
uv run python -m src.scheduler
```

### 3. First-time setup

1. Open `http://localhost:8501`
2. Click **Sign in with Google** and grant calendar permissions
3. You'll be redirected back to the app -- your session is now stored in Postgres

## Deploying to Railway

Railway lets you run each service with its own process, all sharing a single Postgres database.

### 1. Create the project

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) and create a new project
3. Add a **PostgreSQL** plugin -- Railway provisions the database and sets connection variables automatically

### 2. Deploy the Streamlit app

1. Click **New Service** -> **GitHub Repo** and select this repo
2. Under **Settings** -> **Networking**, add a public domain (e.g. `your-app.up.railway.app`)
3. The default `Dockerfile` CMD runs the Streamlit app -- no changes needed
4. Set these environment variables (in **Variables**):

| Variable | Value |
|----------|-------|
| `GOOGLE_CLIENT_ID` | Your OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Your OAuth Client Secret |
| `GOOGLE_REDIRECT_URI` | `https://your-app.up.railway.app` |
| `LLM_PROVIDER` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Your LLM API key |
| `POSTGRES_USER` | From Railway Postgres plugin (use variable reference `${{Postgres.PGUSER}}`) |
| `POSTGRES_PASSWORD` | `${{Postgres.PGPASSWORD}}` |
| `POSTGRES_HOST` | `${{Postgres.PGHOST}}` |
| `POSTGRES_DB` | `${{Postgres.PGDATABASE}}` |

5. Update your Google Cloud Console to add the Railway domain to **Authorized redirect URIs**

### 3. Deploy the scheduler

1. Click **New Service** -> **GitHub Repo** and select the same repo again
2. Under **Settings** -> **Deploy**, set the **Custom Start Command** to:
   ```
   uv run python -m src.scheduler
   ```
3. No public domain needed -- the scheduler only makes outbound requests
4. Copy the same environment variables from the app service (or use shared variables)
5. Additionally set:

| Variable | Value |
|----------|-------|
| `USER_EMAIL` | Email address to send briefs to |
| `GMAIL_ADDRESS` | Gmail address for sending |
| `GMAIL_APP_PASSWORD` | Gmail app password ([generate one here](https://myaccount.google.com/apppasswords)) |
| `BRIEF_HOUR` | Hour to send brief (0-23, default: 8) |
| `BRIEF_MINUTE` | Minute to send brief (0-59, default: 0) |

Both services share the same Postgres database, so OAuth tokens, knowledge base, and reminders are accessible from either service.

## Project Structure

```
ai-assistant/
├── app.py                  # Streamlit application
├── Dockerfile              # Container image
├── docker-compose.yml      # Local dev (app + scheduler + postgres)
├── pyproject.toml          # Dependencies (uv)
├── .env.example            # Environment variable template
└── src/
    ├── config.py           # Configuration
    ├── database.py         # SQLAlchemy models and engine
    ├── assistant.py        # AI assistant (Agno framework)
    ├── knowledge_base.py   # Knowledge base CRUD
    ├── scheduler.py        # Background daily brief scheduler
    ├── tools.py            # Agno tool definitions (calendar ops)
    └── integrations/
        ├── google_auth.py  # Google OAuth flow
        └── calendar.py     # Google Calendar API wrapper
```

## License

MIT
