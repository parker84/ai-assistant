"""Google OAuth2 integration for Streamlit."""
import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import json
from pathlib import Path
from typing import Optional
import os

from src.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    GOOGLE_SCOPES,
    DATA_DIR,
)


def get_google_auth_url() -> str:
    """Generate Google OAuth URL for authentication."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code_for_tokens(code: str) -> Optional[dict]:
    """Exchange authorization code for tokens."""
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GOOGLE_REDIRECT_URI],
                }
            },
            scopes=GOOGLE_SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes),
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }
    except Exception as e:
        st.error(f"Error exchanging code for tokens: {e}")
        return None


def get_credentials_from_tokens(token_data: dict) -> Optional[Credentials]:
    """Create Credentials object from stored token data."""
    try:
        from datetime import datetime
        
        # Parse expiry if present
        expiry = None
        if token_data.get("expiry"):
            try:
                expiry = datetime.fromisoformat(token_data["expiry"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        credentials = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id", GOOGLE_CLIENT_ID),
            client_secret=token_data.get("client_secret", GOOGLE_CLIENT_SECRET),
            scopes=token_data.get("scopes", GOOGLE_SCOPES),
            expiry=expiry,
        )
        
        # Always try to refresh if we have a refresh token and token might be expired
        if credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception:
                # If refresh fails, the token might still be valid
                pass
        
        return credentials
    except Exception as e:
        st.error(f"Error creating credentials: {e}")
        return None


def save_user_tokens(user_email: str, token_data: dict):
    """Save user tokens to file."""
    tokens_dir = DATA_DIR / "tokens"
    tokens_dir.mkdir(exist_ok=True)
    
    # Use a safe filename
    safe_email = user_email.replace("@", "_at_").replace(".", "_")
    token_file = tokens_dir / f"{safe_email}.json"
    
    with open(token_file, "w") as f:
        json.dump(token_data, f)
    
    # Also save as the "last user" for session restoration
    last_user_file = tokens_dir / "last_user.txt"
    with open(last_user_file, "w") as f:
        f.write(user_email)


def load_user_tokens(user_email: str) -> Optional[dict]:
    """Load user tokens from file."""
    tokens_dir = DATA_DIR / "tokens"
    safe_email = user_email.replace("@", "_at_").replace(".", "_")
    token_file = tokens_dir / f"{safe_email}.json"
    
    if token_file.exists():
        with open(token_file, "r") as f:
            return json.load(f)
    return None


def get_last_logged_in_user() -> Optional[str]:
    """Get the email of the last logged in user."""
    tokens_dir = DATA_DIR / "tokens"
    last_user_file = tokens_dir / "last_user.txt"
    
    if last_user_file.exists():
        with open(last_user_file, "r") as f:
            return f.read().strip()
    return None


def clear_last_logged_in_user():
    """Clear the last logged in user (on logout)."""
    tokens_dir = DATA_DIR / "tokens"
    last_user_file = tokens_dir / "last_user.txt"
    
    if last_user_file.exists():
        last_user_file.unlink()


def get_user_info(credentials: Credentials) -> Optional[dict]:
    """Get user info from Google."""
    try:
        from googleapiclient.discovery import build
        
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info
    except Exception as e:
        st.error(f"Error getting user info: {e}")
        return None


def handle_oauth_callback():
    """Handle OAuth callback in Streamlit."""
    query_params = st.query_params
    
    if "code" in query_params:
        code = query_params["code"]
        token_data = exchange_code_for_tokens(code)
        
        if token_data:
            credentials = get_credentials_from_tokens(token_data)
            if credentials:
                user_info = get_user_info(credentials)
                if user_info:
                    # Store in session
                    st.session_state["google_credentials"] = token_data
                    st.session_state["user_info"] = user_info
                    st.session_state["user_email"] = user_info.get("email")
                    st.session_state["authenticated"] = True
                    
                    # Save tokens for persistence
                    save_user_tokens(user_info.get("email"), token_data)
                    
                    # Clear URL params
                    st.query_params.clear()
                    return True
    return False


def check_authentication() -> bool:
    """Check if user is authenticated."""
    if st.session_state.get("authenticated"):
        return True
    
    # Try to handle OAuth callback
    if handle_oauth_callback():
        return True
    
    # Try to restore session from saved tokens
    last_user = get_last_logged_in_user()
    if last_user:
        token_data = load_user_tokens(last_user)
        if token_data:
            credentials = get_credentials_from_tokens(token_data)
            if credentials:
                # Try to get user info to verify credentials still work
                user_info = get_user_info(credentials)
                if user_info:
                    # Restore session
                    st.session_state["google_credentials"] = token_data
                    st.session_state["user_info"] = user_info
                    st.session_state["user_email"] = user_info.get("email")
                    st.session_state["authenticated"] = True
                    return True
    
    return False


def logout():
    """Clear authentication state."""
    keys_to_clear = ["google_credentials", "user_info", "user_email", "authenticated"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear persistent login
    clear_last_logged_in_user()
