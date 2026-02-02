"""Streamlit AI Assistant Application."""
import streamlit as st
from datetime import datetime, timedelta
import pytz

from src.config import APP_NAME, TIMEZONE, GOOGLE_CLIENT_ID
from src.integrations.google_auth import (
    get_google_auth_url,
    check_authentication,
    get_credentials_from_tokens,
    logout,
)
from src.integrations.calendar import (
    get_todays_events,
    get_upcoming_events,
    get_calendar_summary,
    create_event,
    create_recurring_birthday,
    create_interview_event,
    find_free_slots,
)
from src.knowledge_base import KnowledgeBase
from src.assistant import AIAssistant

# Page config
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "assistant" not in st.session_state:
        st.session_state.assistant = None
    if "knowledge_base" not in st.session_state:
        st.session_state.knowledge_base = None


def render_login_page():
    """Render the login page."""
    st.title(f"🤖 {APP_NAME}")
    st.markdown("### Your Personal AI Assistant")
    
    st.markdown("""
    Welcome! This assistant helps you:
    - 📅 Manage your Google Calendar
    - 🧠 Maintain a personal knowledge base
    - ⏰ Get daily reminders and briefs
    - 📝 Add events and track important dates
    
    Please sign in with Google to get started.
    """)
    
    if not GOOGLE_CLIENT_ID:
        st.error("Google OAuth is not configured. Please set GOOGLE_CLIENT_ID in your .env file.")
        st.markdown("""
        ### Setup Instructions:
        1. Go to [Google Cloud Console](https://console.cloud.google.com)
        2. Create a new project or select existing
        3. Enable the Google Calendar API
        4. Go to Credentials → Create Credentials → OAuth 2.0 Client ID
        5. Set application type to "Web application"
        6. Add `http://localhost:8501` to Authorized redirect URIs
        7. Copy the Client ID and Client Secret to your `.env` file
        """)
        return
    
    auth_url = get_google_auth_url()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.link_button(
            "🔐 Sign in with Google",
            auth_url,
            use_container_width=True,
        )


def render_sidebar():
    """Render the sidebar."""
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.get('user_info', {}).get('name', 'User')}")
        st.markdown(f"*{st.session_state.get('user_email', '')}*")
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "Navigation",
            ["💬 Chat", "📅 Calendar", "🧠 Knowledge Base", "📊 Daily Brief", "⚙️ Settings"],
            label_visibility="collapsed",
        )
        
        st.divider()
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
        
        return page


def render_chat_page():
    """Render the chat interface."""
    st.title("💬 Chat with Assistant")
    
    # Get credentials and calendar context
    credentials = None
    calendar_context = ""
    if st.session_state.get("google_credentials"):
        credentials = get_credentials_from_tokens(st.session_state["google_credentials"])
        if credentials:
            try:
                events = get_todays_events(credentials)
                calendar_context = get_calendar_summary(credentials, days=3)
            except Exception as e:
                st.warning(f"Could not load calendar: {e}")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                if st.session_state.assistant:
                    # Check if this should update knowledge base
                    kb_update = st.session_state.assistant.update_knowledge_from_chat(prompt)
                    if kb_update:
                        st.info(kb_update)
                    
                    # Get response
                    response = st.session_state.assistant.chat(prompt, calendar_context)
                else:
                    response = "Assistant not initialized. Please check your API keys."
                
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Quick actions
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📅 What's on my calendar today?", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "What's on my calendar today?"})
            st.rerun()
    with col2:
        if st.button("💡 What am I missing?", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "Analyze my calendar and tell me what I might be missing"})
            st.rerun()
    with col3:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            if st.session_state.assistant:
                st.session_state.assistant.clear_conversation()
            st.rerun()


def render_calendar_page():
    """Render the calendar management page."""
    st.title("📅 Calendar Management")
    
    credentials = None
    if st.session_state.get("google_credentials"):
        credentials = get_credentials_from_tokens(st.session_state["google_credentials"])
    
    if not credentials:
        st.warning("Please authenticate with Google to access your calendar.")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 View Events", "➕ Add Event", "🎂 Add Birthday", "👥 Schedule Interview"])
    
    with tab1:
        st.subheader("Upcoming Events")
        days = st.slider("Show events for next N days:", 1, 30, 7)
        
        try:
            events = get_upcoming_events(credentials, days)
            
            if events:
                for event in events:
                    start = event.get("start", {})
                    if "dateTime" in start:
                        event_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                        time_str = event_time.strftime("%A, %B %d at %I:%M %p")
                    else:
                        time_str = f"All day - {start.get('date', '')}"
                    
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{event.get('summary', 'No title')}**")
                            st.markdown(f"🕐 {time_str}")
                            if event.get("location"):
                                st.markdown(f"📍 {event.get('location')}")
                        st.divider()
            else:
                st.info("No upcoming events found.")
        except Exception as e:
            st.error(f"Error loading events: {e}")
    
    with tab2:
        st.subheader("Add New Event")
        
        with st.form("add_event_form"):
            summary = st.text_input("Event Title *")
            description = st.text_area("Description")
            
            col1, col2 = st.columns(2)
            with col1:
                event_date = st.date_input("Date *", min_value=datetime.now().date())
                start_time = st.time_input("Start Time *")
            with col2:
                duration = st.selectbox("Duration", [15, 30, 45, 60, 90, 120], index=3)
                location = st.text_input("Location")
            
            attendees_text = st.text_input("Attendees (comma-separated emails)")
            
            submitted = st.form_submit_button("Create Event", use_container_width=True)
            
            if submitted and summary:
                try:
                    tz = pytz.timezone(TIMEZONE)
                    start_datetime = tz.localize(datetime.combine(event_date, start_time))
                    end_datetime = start_datetime + timedelta(minutes=duration)
                    
                    attendees = [e.strip() for e in attendees_text.split(",") if e.strip()] if attendees_text else None
                    
                    event = create_event(
                        credentials=credentials,
                        summary=summary,
                        start_time=start_datetime,
                        end_time=end_datetime,
                        description=description,
                        location=location,
                        attendees=attendees,
                    )
                    
                    st.success(f"Event created: {event.get('summary')}")
                except Exception as e:
                    st.error(f"Error creating event: {e}")
    
    with tab3:
        st.subheader("Add Recurring Birthday")
        
        with st.form("add_birthday_form"):
            name = st.text_input("Person's Name *")
            birthday = st.date_input("Birthday *")
            
            submitted = st.form_submit_button("Add Birthday", use_container_width=True)
            
            if submitted and name:
                try:
                    tz = pytz.timezone(TIMEZONE)
                    birthday_datetime = tz.localize(datetime.combine(birthday, datetime.min.time()))
                    
                    event = create_recurring_birthday(
                        credentials=credentials,
                        name=name,
                        birthday_date=birthday_datetime,
                    )
                    
                    st.success(f"Birthday added for {name}! It will repeat every year.")
                except Exception as e:
                    st.error(f"Error adding birthday: {e}")
    
    with tab4:
        st.subheader("Schedule Interview")
        
        with st.form("schedule_interview_form"):
            candidate_name = st.text_input("Candidate Name *")
            interviewers = st.text_input("Interviewers (comma-separated emails) *")
            
            col1, col2 = st.columns(2)
            with col1:
                interview_date = st.date_input("Date *", min_value=datetime.now().date())
                interview_time = st.time_input("Time *")
            with col2:
                duration = st.selectbox("Duration (minutes)", [30, 45, 60, 90], index=2)
            
            description = st.text_area("Interview Notes/Description")
            
            # Show available slots
            if st.form_submit_button("Find Available Slots"):
                try:
                    tz = pytz.timezone(TIMEZONE)
                    check_date = tz.localize(datetime.combine(interview_date, datetime.min.time()))
                    slots = find_free_slots(credentials, check_date, duration)
                    
                    if slots:
                        st.info("Available time slots:")
                        for slot in slots:
                            st.write(f"• {slot['start'].strftime('%I:%M %p')} - {slot['end'].strftime('%I:%M %p')}")
                    else:
                        st.warning("No available slots found for this duration.")
                except Exception as e:
                    st.error(f"Error finding slots: {e}")
            
            submitted = st.form_submit_button("Schedule Interview", use_container_width=True)
            
            if submitted and candidate_name and interviewers:
                try:
                    tz = pytz.timezone(TIMEZONE)
                    start_datetime = tz.localize(datetime.combine(interview_date, interview_time))
                    interviewer_list = [e.strip() for e in interviewers.split(",") if e.strip()]
                    
                    event = create_interview_event(
                        credentials=credentials,
                        candidate_name=candidate_name,
                        interviewers=interviewer_list,
                        start_time=start_datetime,
                        duration_minutes=duration,
                        description=description,
                    )
                    
                    st.success(f"Interview scheduled with {candidate_name}!")
                except Exception as e:
                    st.error(f"Error scheduling interview: {e}")


def render_knowledge_base_page():
    """Render the knowledge base management page."""
    st.title("🧠 Knowledge Base")
    
    st.markdown("""
    Your knowledge base stores personal information, reminders, and context that helps the assistant 
    provide better, more personalized responses.
    """)
    
    if not st.session_state.knowledge_base:
        st.warning("Knowledge base not initialized.")
        return
    
    kb = st.session_state.knowledge_base
    
    tab1, tab2, tab3 = st.tabs(["📝 Edit Knowledge Base", "⏰ Reminders", "🔍 Search"])
    
    with tab1:
        st.subheader("Edit Your Knowledge Base")
        
        current_content = kb.get_knowledge_base()
        
        new_content = st.text_area(
            "Knowledge Base Content (Markdown)",
            value=current_content,
            height=500,
            help="Edit your knowledge base. Use markdown formatting.",
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Changes", use_container_width=True):
                if kb.update_knowledge_base(new_content):
                    st.success("Knowledge base updated!")
                else:
                    st.error("Failed to update knowledge base.")
        with col2:
            if st.button("🔄 Reset to Template", use_container_width=True):
                kb._init_knowledge_base()
                st.rerun()
        
        st.divider()
        
        # Quick add section
        st.subheader("Quick Add")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            section = st.selectbox(
                "Section",
                ["About Me", "Important People", "Work Context", "Preferences", "Custom Reminders", "Notes"],
            )
        with col2:
            new_item = st.text_input("Content to add")
        
        if st.button("➕ Add to Section"):
            if new_item:
                if kb.append_to_knowledge_base(section, f"\n- {new_item}"):
                    st.success(f"Added to {section}!")
                    st.rerun()
                else:
                    st.error("Failed to add content.")
    
    with tab2:
        st.subheader("Manage Reminders")
        
        reminders = kb.get_reminders()
        
        # Add new reminder
        with st.expander("➕ Add New Reminder", expanded=True):
            reminder_text = st.text_input("Reminder text")
            reminder_type = st.selectbox("Type", ["daily", "recurring", "one_time"])
            
            if st.button("Add Reminder"):
                if reminder_text:
                    if kb.add_reminder(reminder_text, reminder_type):
                        st.success("Reminder added!")
                        st.rerun()
        
        # Display reminders
        st.divider()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Daily Reminders**")
            for r in reminders.get("daily_reminders", []):
                st.markdown(f"• {r['text']}")
                if st.button(f"🗑️", key=f"del_daily_{r['id']}"):
                    kb.remove_reminder(r["id"])
                    st.rerun()
        
        with col2:
            st.markdown("**Recurring Reminders**")
            for r in reminders.get("recurring_reminders", []):
                st.markdown(f"• {r['text']}")
                if st.button(f"🗑️", key=f"del_recurring_{r['id']}"):
                    kb.remove_reminder(r["id"])
                    st.rerun()
        
        with col3:
            st.markdown("**One-time Reminders**")
            for r in reminders.get("one_time_reminders", []):
                st.markdown(f"• {r['text']}")
                if st.button(f"🗑️", key=f"del_onetime_{r['id']}"):
                    kb.remove_reminder(r["id"])
                    st.rerun()
    
    with tab3:
        st.subheader("Search Knowledge Base")
        
        query = st.text_input("Search for...")
        
        if query:
            results = kb.search_knowledge_base(query)
            
            if results:
                st.markdown(f"**Found {len(results)} result(s):**")
                for i, result in enumerate(results):
                    with st.expander(f"Result {i + 1}"):
                        st.markdown(result)
            else:
                st.info("No results found.")


def render_daily_brief_page():
    """Render the daily brief page."""
    st.title("📊 Daily Brief")
    
    credentials = None
    if st.session_state.get("google_credentials"):
        credentials = get_credentials_from_tokens(st.session_state["google_credentials"])
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🔄 Generate Today's Brief", use_container_width=True):
            with st.spinner("Generating your daily brief..."):
                try:
                    events = []
                    if credentials:
                        events = get_todays_events(credentials)
                    
                    if st.session_state.assistant:
                        brief = st.session_state.assistant.generate_daily_brief(events)
                        st.session_state["daily_brief"] = brief
                    else:
                        st.error("Assistant not configured. Please check your API keys.")
                except Exception as e:
                    st.error(f"Error generating brief: {e}")
    
    with col2:
        if st.button("📋 Analyze My Calendar", use_container_width=True):
            with st.spinner("Analyzing your calendar..."):
                try:
                    if credentials:
                        events = get_upcoming_events(credentials, days=7)
                        
                        if st.session_state.assistant:
                            analysis = st.session_state.assistant.analyze_calendar(events)
                            st.session_state["calendar_analysis"] = analysis
                        else:
                            st.error("Assistant not configured.")
                    else:
                        st.warning("Please authenticate with Google to analyze your calendar.")
                except Exception as e:
                    st.error(f"Error analyzing calendar: {e}")
    
    st.divider()
    
    # Display daily brief
    if st.session_state.get("daily_brief"):
        st.markdown("### Today's Brief")
        st.markdown(f'<div class="daily-brief">{st.session_state["daily_brief"]}</div>', unsafe_allow_html=True)
    
    # Display calendar analysis
    if st.session_state.get("calendar_analysis"):
        st.markdown("### Calendar Analysis")
        st.markdown(st.session_state["calendar_analysis"])
    
    # Show today's events
    if credentials:
        st.divider()
        st.markdown("### Today's Calendar Events")
        
        try:
            events = get_todays_events(credentials)
            
            if events:
                for event in events:
                    start = event.get("start", {})
                    if "dateTime" in start:
                        event_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                        time_str = event_time.strftime("%I:%M %p")
                    else:
                        time_str = "All day"
                    
                    st.markdown(f'<div class="calendar-event">🕐 {time_str} - **{event.get("summary", "No title")}**</div>', unsafe_allow_html=True)
            else:
                st.info("No events scheduled for today.")
        except Exception as e:
            st.error(f"Error loading events: {e}")


def render_settings_page():
    """Render the settings page."""
    st.title("⚙️ Settings")
    
    st.markdown("### API Configuration")
    st.info("API keys are configured in the `.env` file for security. Restart the app after making changes.")
    
    st.markdown("""
    **Required Environment Variables:**
    - `GOOGLE_CLIENT_ID` - Google OAuth Client ID
    - `GOOGLE_CLIENT_SECRET` - Google OAuth Client Secret
    - `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` - LLM API key
    - `LLM_PROVIDER` - "anthropic" or "openai"
    - `LLM_MODEL` - Model name (e.g., "claude-sonnet-4-20250514")
    """)
    
    st.divider()
    
    st.markdown("### Account Info")
    if st.session_state.get("user_info"):
        user_info = st.session_state["user_info"]
        st.markdown(f"**Name:** {user_info.get('name', 'N/A')}")
        st.markdown(f"**Email:** {user_info.get('email', 'N/A')}")
    
    st.divider()
    
    st.markdown("### Data Management")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Export Knowledge Base", use_container_width=True):
            if st.session_state.knowledge_base:
                content = st.session_state.knowledge_base.get_knowledge_base()
                st.download_button(
                    "Download Knowledge Base",
                    content,
                    file_name="knowledge_base.md",
                    mime="text/markdown",
                )
    
    with col2:
        if st.button("🗑️ Clear Conversation History", use_container_width=True):
            st.session_state.messages = []
            if st.session_state.assistant:
                st.session_state.assistant.clear_conversation()
            st.success("Conversation history cleared!")


def main():
    """Main application entry point."""
    init_session_state()
    
    # Check authentication
    if not check_authentication():
        render_login_page()
        return
    
    # Initialize assistant and knowledge base for authenticated user
    user_email = st.session_state.get("user_email", "")
    
    if user_email and not st.session_state.assistant:
        st.session_state.assistant = AIAssistant(user_email)
        st.session_state.knowledge_base = KnowledgeBase(user_email)
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Render selected page
    if page == "💬 Chat":
        render_chat_page()
    elif page == "📅 Calendar":
        render_calendar_page()
    elif page == "🧠 Knowledge Base":
        render_knowledge_base_page()
    elif page == "📊 Daily Brief":
        render_daily_brief_page()
    elif page == "⚙️ Settings":
        render_settings_page()


if __name__ == "__main__":
    main()
