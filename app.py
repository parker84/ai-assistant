"""Streamlit AI Assistant Application."""
import streamlit as st
import time
from src.config import APP_NAME, TIMEZONE, GOOGLE_CLIENT_ID

from src.integrations.google_auth import (
    get_google_auth_url,
    check_authentication,
    get_credentials_from_tokens,
    logout,
)
from src.tools import set_credentials, create_recurring_all_day_event
from src.knowledge_base import KnowledgeBase
from src.assistant import AIAssistant
from src.logging_utils import get_logger

logger = get_logger(__name__)

# Page config
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🦾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Cyberpunk CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #0a0a0f 0%, #0f1419 50%, #0a0f14 100%);
    }
    
    /* Headers */
    h1 {
        font-family: 'Orbitron', monospace !important;
        color: #00ffcc !important;
        text-shadow: 0 0 20px rgba(0, 255, 204, 0.5);
        letter-spacing: 2px;
    }
    
    h2, h3 {
        font-family: 'Space Mono', monospace !important;
        color: #00d4aa !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1419 0%, #1a1f2e 100%);
        border-right: 1px solid rgba(0, 255, 204, 0.2);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        font-family: 'Space Mono', monospace;
    }
    
    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: rgba(15, 20, 30, 0.8);
        border: 1px solid rgba(0, 255, 204, 0.15);
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }
    
    /* Buttons */
    .stButton > button {
        font-family: 'Space Mono', monospace;
        background: linear-gradient(135deg, rgba(0, 255, 204, 0.1) 0%, rgba(0, 212, 170, 0.2) 100%);
        border: 1px solid rgba(0, 255, 204, 0.4);
        color: #00ffcc;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(0, 255, 204, 0.2) 0%, rgba(0, 212, 170, 0.3) 100%);
        border-color: #00ffcc;
        box-shadow: 0 0 20px rgba(0, 255, 204, 0.3);
    }
    
    /* Input fields */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: rgba(15, 20, 30, 0.8);
        border: 1px solid rgba(0, 255, 204, 0.3);
        color: #e0e0e0;
        font-family: 'Inter', sans-serif;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #00ffcc;
        box-shadow: 0 0 10px rgba(0, 255, 204, 0.2);
    }
    
    /* Chat input */
    [data-testid="stChatInput"] {
        background: rgba(15, 20, 30, 0.9);
        border: 1px solid rgba(0, 255, 204, 0.3);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Space Mono', monospace;
        background: rgba(0, 255, 204, 0.05);
        border: 1px solid rgba(0, 255, 204, 0.2);
        border-radius: 8px;
        color: #8892b0;
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(0, 255, 204, 0.15);
        border-color: #00ffcc;
        color: #00ffcc;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-family: 'Orbitron', monospace !important;
        color: #00ffcc !important;
    }
    
    /* Divider */
    hr {
        border-color: rgba(0, 255, 204, 0.2);
    }
    
    /* Radio buttons in sidebar */
    .stRadio > label {
        font-family: 'Space Mono', monospace;
    }
    
    /* Custom classes */
    .cyber-title {
        font-family: 'Orbitron', monospace;
        color: #00ffcc;
        text-shadow: 0 0 30px rgba(0, 255, 204, 0.6);
        font-size: 2.5rem;
        letter-spacing: 4px;
    }
    
    .cyber-subtitle {
        font-family: 'Space Mono', monospace;
        color: #8892b0;
        letter-spacing: 2px;
    }
    
    .glow-box {
        background: rgba(0, 255, 204, 0.05);
        border: 1px solid rgba(0, 255, 204, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 0 30px rgba(0, 255, 204, 0.1);
    }
</style>
""", unsafe_allow_html=True)


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
    st.title(f"🦾 {APP_NAME}")
    st.markdown("### Your AI Assistant")
    
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
            ["🦾 Auto", "🧠 Knowledge Base", "📊 Daily Brief", "🛒 Grocery List", "✅ Todo List"],
            label_visibility="collapsed",
        )
        
        st.divider()
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
        
        return page


def render_chat_page():
    """Render the chat interface."""
    st.title("🦾 Auto")
    st.caption("Your AI Assistant")
    
    # Check if there's a pending message that needs a response (from button clicks)
    pending_prompt = None
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        if not st.session_state.get("last_processed_message"):
            st.session_state["last_processed_message"] = None
        
        last_user_msg = st.session_state.messages[-1]["content"]
        if st.session_state["last_processed_message"] != last_user_msg:
            pending_prompt = last_user_msg
    
    # Display chat history (except pending message which we'll show with response)
    messages_to_display = st.session_state.messages
    if pending_prompt:
        messages_to_display = st.session_state.messages[:-1]
    
    for message in messages_to_display:
        avatar = "💁‍♀️" if message["role"] == "user" else ":material/smart_toy:"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])
    
    # Process pending message from button click
    if pending_prompt:
        with st.chat_message("user", avatar="💁‍♀️"):
            st.markdown(pending_prompt)
        
        with st.chat_message("assistant", avatar=":material/smart_toy:"):
            with st.spinner("Thinking..."):
                if st.session_state.assistant:
                    response = st.session_state.assistant.chat(pending_prompt)
                else:
                    response = "Assistant not initialized. Please check your API keys."
                
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.session_state["last_processed_message"] = pending_prompt
    
    # Chat input
    if prompt := st.chat_input("Ask me anything..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state["last_processed_message"] = prompt
        
        with st.chat_message("user", avatar="💁‍♀️"):
            st.markdown(prompt)
        
        # Get assistant response
        with st.chat_message("assistant", avatar=":material/smart_toy:"):
            with st.spinner("Thinking..."):
                if st.session_state.assistant:
                    response = st.session_state.assistant.chat(prompt)
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
            st.session_state["last_processed_message"] = None
            if st.session_state.assistant:
                st.session_state.assistant.clear_conversation()
            st.rerun()
    

def render_knowledge_base_page():
    """Render the knowledge base management page."""
    st.title("🧠 Knowledge Base")
    
    if not st.session_state.knowledge_base:
        st.warning("Knowledge base not initialized.")
        return
    
    kb = st.session_state.knowledge_base
    
    tab_markdown, tab_memories = st.tabs(["🖊️ Knowledge Base", "🤖 Learned Memories"])
    
    with tab_markdown:
        current_content = kb.get_knowledge_base()
        
        new_content = st.text_area(
            "Edit your knowledge base (Markdown)",
            value=current_content,
            height=500,
            label_visibility="collapsed",
            key="kb_editor",
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save", use_container_width=True, key="kb_save"):
                if kb.update_knowledge_base(new_content):
                    st.success("Saved!")
                else:
                    st.error("Failed to save.")
        with col2:
            if st.button("🔄 Reset to Template", use_container_width=True, key="kb_reset"):
                kb._init_knowledge_base()
                st.rerun()
    
    with tab_memories:
        st.subheader("Learned Memories")
        st.caption("Memories the AI has learned from your conversations (Agno learning system)")
        
        if not st.session_state.assistant:
            st.info("Start chatting with the assistant to build up learned memories.")
            return
        
        try:
            memories = st.session_state.assistant.get_learned_memories()
        except Exception as e:
            st.error(f"Error loading memories: {e}")
            memories = {"user_profile": [], "entities": [], "session_context": []}
        
        has_any = (
            bool(memories.get("user_profile"))
            or bool(memories.get("entities"))
            or bool(memories.get("session_context"))
        )
        
        if not has_any:
            st.info("No learned memories yet. Chat with the assistant and it will remember things about you.")
            return
        
        if memories.get("user_profile"):
            st.markdown("#### 👤 User Profile")
            for i, item in enumerate(memories["user_profile"]):
                with st.expander(f"Profile {i + 1}", expanded=(i == 0)):
                    if isinstance(item, dict):
                        st.json(item)
                    else:
                        st.write(item)
        
        if memories.get("entities"):
            st.markdown("#### 📌 Entities")
            for i, item in enumerate(memories["entities"]):
                with st.expander(f"Entity {i + 1}", expanded=(i == 0)):
                    if isinstance(item, dict):
                        st.json(item)
                    else:
                        st.write(item)
        
        if memories.get("session_context"):
            st.markdown("#### 📋 Session Context")
            for i, item in enumerate(memories["session_context"]):
                with st.expander(f"Session {i + 1}", expanded=(i == 0)):
                    if isinstance(item, dict):
                        st.json(item)
                    else:
                        st.write(item)
        
        if st.button("🔄 Refresh Memories", use_container_width=True, key="refresh_memories"):
            st.rerun()


def render_daily_brief_page():
    """Render the daily brief page."""
    st.title("📊 Daily Brief")
    
    kb = st.session_state.knowledge_base
    credentials = None
    if st.session_state.get("google_credentials"):
        credentials = get_credentials_from_tokens(st.session_state["google_credentials"])
    
    # Settings expander: Personal & Professional reminders
    if not kb:
        st.warning("Knowledge base not initialized.")
        return
    
    with st.expander("⚙️ Reminders", expanded=False):
        st.caption("One personal and one professional reminder are randomly picked for each brief.")
        
        reminders = kb.get_reminders()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Personal 💁‍♀️**")
            for i, r in enumerate(reminders.get("personal", [])):
                rc1, rc2 = st.columns([4, 1])
                with rc1:
                    st.text(r)
                with rc2:
                    if st.button("🗑️", key=f"del_personal_{i}"):
                        kb.remove_reminder("personal", i)
                        st.rerun()
            new_personal = st.text_input("Add personal reminder", key="new_personal_reminder", placeholder="e.g. Do something spontaneous for Kennedy today")
            if st.button("Add", key="add_personal") and new_personal:
                kb.add_reminder("personal", new_personal)
                st.rerun()
        
        with col2:
            st.markdown("**Professional 💻**")
            for i, r in enumerate(reminders.get("professional", [])):
                rc1, rc2 = st.columns([4, 1])
                with rc1:
                    st.text(r)
                with rc2:
                    if st.button("🗑️", key=f"del_professional_{i}"):
                        kb.remove_reminder("professional", i)
                        st.rerun()
            new_professional = st.text_input("Add professional reminder", key="new_professional_reminder", placeholder="e.g. Be a coach not a player today")
            if st.button("Add", key="add_professional") and new_professional:
                kb.add_reminder("professional", new_professional)
                st.rerun()

    with st.expander("📆 Crucial Calendar Events", expanded=False):
        st.caption("Recurring all-day events (birthdays, anniversaries). Won't block meetings.")
        
        crucial_events = kb.get_crucial_events()
        
        for i, ev in enumerate(crucial_events):
            ec1, ec2, ec3 = st.columns([3, 2, 1])
            with ec1:
                st.text(ev["name"])
            with ec2:
                st.caption(ev["date"])
            with ec3:
                if st.button("🗑️", key=f"del_crucial_{i}"):
                    kb.remove_crucial_event(i)
                    st.rerun()
        
        col_a, col_b = st.columns(2)
        with col_a:
            new_name = st.text_input("Event name", key="new_crucial_name", placeholder="e.g. Mom's Birthday")
        with col_b:
            new_date = st.text_input("Date (MM-DD or 05-2nd-sun)", key="new_crucial_date", placeholder="e.g. 01-21 or 05-2nd-sun")
        if st.button("Add event", key="add_crucial") and new_name and new_date:
            kb.add_crucial_event(new_name, new_date)
            st.rerun()
        
        if credentials and crucial_events:
            st.divider()
            if st.button("➕ Add all to Google Calendar", key="sync_crucial_to_calendar"):
                set_credentials(credentials)
                results = []
                for ev in crucial_events:
                    r = create_recurring_all_day_event(ev["name"], ev["date"])
                    results.append(f"{ev['name']}: {r}")
                st.success("Synced!")
                for r in results:
                    st.caption(r)
    
    st.divider()
    
    # Auto-generate brief on first load if not already generated
    if "daily_brief" not in st.session_state or not st.session_state.get("daily_brief"):
        with st.spinner("Generating your daily brief..."):
            try:
                if st.session_state.assistant:
                    brief = st.session_state.assistant.generate_daily_brief()
                    st.session_state["daily_brief"] = brief
                else:
                    st.session_state["daily_brief"] = "Assistant not configured. Please check your API keys."
            except Exception as e:
                st.session_state["daily_brief"] = f"Error generating brief: {e}"
    
    # Display the brief
    st.markdown(st.session_state.get("daily_brief", ""))
    
    st.divider()
    
    # Regenerate button
    if st.button("🔄 Regenerate", use_container_width=True):
        with st.spinner("Regenerating..."):
            try:
                if st.session_state.assistant:
                    brief = st.session_state.assistant.generate_daily_brief()
                    st.session_state["daily_brief"] = brief
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


def render_grocery_page():
    """Render the grocery list management page."""
    st.title("🛒 Grocery List")

    kb = st.session_state.knowledge_base
    if not kb:
        st.warning("Knowledge base not initialized.")
        return

    items = kb.get_grocery_items()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Recurring (weekly staples)**")
        for i, item in enumerate(items.get("recurring", [])):
            rc1, rc2 = st.columns([4, 1])
            with rc1:
                st.text(item)
            with rc2:
                if st.button("🗑️", key=f"del_recurring_{i}"):
                    kb.remove_grocery_item("recurring", i)
                    st.rerun()
        new_recurring = st.text_input("Add recurring item", key="new_recurring_grocery", placeholder="e.g. Milk")
        if st.button("Add", key="add_recurring_grocery") and new_recurring:
            kb.add_grocery_item("recurring", new_recurring)
            st.rerun()

    with col2:
        st.markdown("**One-time (this week only)**")
        for i, item in enumerate(items.get("one-time", [])):
            rc1, rc2 = st.columns([4, 1])
            with rc1:
                st.text(item)
            with rc2:
                if st.button("🗑️", key=f"del_onetime_{i}"):
                    kb.remove_grocery_item("one-time", i)
                    st.rerun()
        new_onetime = st.text_input("Add one-time item", key="new_onetime_grocery", placeholder="e.g. Birthday cake")
        if st.button("Add", key="add_onetime_grocery") and new_onetime:
            kb.add_grocery_item("one-time", new_onetime)
            st.rerun()

        if items.get("one-time"):
            st.divider()
            if st.button("🧹 Clear all one-time items", key="clear_onetime_grocery", use_container_width=True):
                count = kb.clear_onetime_grocery_items()
                st.toast(f"Cleared {count} one-time item{'s' if count != 1 else ''}.")
                st.rerun()


def render_todo_page():
    """Render the todo list management page."""
    st.title("✅ Todo List")

    kb = st.session_state.knowledge_base
    if not kb:
        st.warning("Knowledge base not initialized.")
        return

    items = kb.get_todo_items()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Personal 💁‍♀️**")
        for i, item in enumerate(items.get("personal", [])):
            rc1, rc2 = st.columns([4, 1])
            with rc1:
                st.text(item)
            with rc2:
                if st.button("✅", key=f"del_todo_personal_{i}"):
                    kb.remove_todo_item("personal", i)
                    st.toast(f"{item} marked as done ✅")
                    time.sleep(2)
                    st.rerun()
        new_personal = st.text_input("Add personal todo", key="new_personal_todo", placeholder="e.g. Book dentist appointment")
        if st.button("Add", key="add_personal_todo") and new_personal:
            kb.add_todo_item("personal", new_personal)
            st.rerun()

        if items.get("personal"):
            st.divider()
            if st.button("🧹 Clear all personal todos", key="clear_personal_todo", use_container_width=True):
                count = kb.clear_todo_items("personal")
                st.toast(f"Cleared {count} personal todo{'s' if count != 1 else ''}.")
                st.rerun()

    with col2:
        st.markdown("**Work 💻**")
        for i, item in enumerate(items.get("work", [])):
            rc1, rc2 = st.columns([4, 1])
            with rc1:
                st.text(item)
            with rc2:
                if st.button("✅", key=f"del_todo_work_{i}"):
                    kb.remove_todo_item("work", i)
                    st.toast(f"{item} marked as done ✅")
                    time.sleep(2)
                    st.rerun()
        new_work = st.text_input("Add work todo", key="new_work_todo", placeholder="e.g. Review PR #42")
        if st.button("Add", key="add_work_todo") and new_work:
            kb.add_todo_item("work", new_work)
            st.rerun()

        if items.get("work"):
            st.divider()
            if st.button("🧹 Clear all work todos", key="clear_work_todo", use_container_width=True):
                count = kb.clear_todo_items("work")
                st.toast(f"Cleared {count} work todo{'s' if count != 1 else ''}.")
                st.rerun()


def main():
    """Main application entry point."""
    init_session_state()
    
    # Check authentication
    if not check_authentication():
        render_login_page()
        return
    
    # Initialize assistant and knowledge base for authenticated user
    user_email = st.session_state.get("user_email", "")
    credentials = None
    if st.session_state.get("google_credentials"):
        credentials = get_credentials_from_tokens(st.session_state["google_credentials"])
    
    if user_email and not st.session_state.assistant:
        st.session_state.assistant = AIAssistant(user_email, credentials=credentials)
        st.session_state.knowledge_base = KnowledgeBase(user_email)
    elif user_email and st.session_state.assistant and credentials:
        # Update credentials if they've changed
        st.session_state.assistant.update_credentials(credentials)
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Render selected page
    if page == "🦾 Auto":
        render_chat_page()
    elif page == "🧠 Knowledge Base":
        render_knowledge_base_page()
    elif page == "📊 Daily Brief":
        render_daily_brief_page()
    elif page == "🛒 Grocery List":
        render_grocery_page()
    elif page == "✅ Todo List":
        render_todo_page()


if __name__ == "__main__":
    main()
