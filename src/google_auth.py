"""Google OAuth2 authentication for Streamlit."""

import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import json
from pathlib import Path

from src.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    GOOGLE_SCOPES,
    DATA_DIR,
)


def get_google_auth_url() -> str:
    """Generate Google OAuth2 authorization URL."""
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
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens."""
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
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)
    
    credentials = flow.credentials
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes),
    }


def get_credentials_from_session() -> Credentials | None:
    """Get Google credentials from Streamlit session state."""
    if "google_credentials" not in st.session_state:
        return None
    
    creds_data = st.session_state.google_credentials
    credentials = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=creds_data.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=creds_data.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=creds_data.get("scopes", GOOGLE_SCOPES),
    )
    
    # Refresh if expired
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        # Update session state with new token
        st.session_state.google_credentials["token"] = credentials.token
    
    return credentials


def save_credentials_to_file(user_email: str, credentials_data: dict):
    """Save credentials to a file for persistence."""
    creds_file = DATA_DIR / f"credentials_{user_email.replace('@', '_at_')}.json"
    with open(creds_file, "w") as f:
        json.dump(credentials_data, f)


def load_credentials_from_file(user_email: str) -> dict | None:
    """Load credentials from file."""
    creds_file = DATA_DIR / f"credentials_{user_email.replace('@', '_at_')}.json"
    if creds_file.exists():
        with open(creds_file, "r") as f:
            return json.load(f)
    return None


def get_user_info(credentials: Credentials) -> dict:
    """Get user info from Google."""
    from googleapiclient.discovery import build
    
    service = build("oauth2", "v2", credentials=credentials)
    user_info = service.userinfo().get().execute()
    return user_info


def logout():
    """Clear authentication state."""
    if "google_credentials" in st.session_state:
        del st.session_state.google_credentials
    if "user_info" in st.session_state:
        del st.session_state.user_info
    if "authenticated" in st.session_state:
        del st.session_state.authenticated
