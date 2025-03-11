import streamlit as st
import os
from dotenv import load_dotenv
import logging
import base64
import json
import time

# Import logging utility
from utils.logging_utils import setup_logging

# Import components
from components.upload import show_upload_page
from components.analyze import show_analyze_page
from components.chat import show_chat_page

# Import state management
from models.session_state import initialize_session_state

# Import API clients
from utils.api_clients import initialize_api_clients

# Import custom authentication
from utils.custom_auth import is_authenticated, AUTH_ENABLED, get_username, logout, redirect_to_auth, check_auth

# First, check for token from file system (set by auth_server.py)
LOCAL_ENV_FILE = ".streamlit_auth_env"
if os.path.exists(LOCAL_ENV_FILE):
    logger = logging.getLogger(__name__)
    logger.info(f"Loading auth token from {LOCAL_ENV_FILE}")
    with open(LOCAL_ENV_FILE, 'r') as f:
        content = f.read().strip()
        if content.startswith('AUTH_TOKEN='):
            token = content[11:].strip()
            if token:
                # Store token in environment variable
                os.environ['STREAMLIT_AUTH_TOKEN'] = token
                logger.info("Auth token loaded from file")

# Configure page with hidden sidebar if auth required but not authenticated
hide_streamlit_ui = os.environ.get('HIDE_STREAMLIT_UI', 'false').lower() == 'true'

st.set_page_config(
    page_title="Video Analysis and Chat with LLM's",
    layout="wide",
    initial_sidebar_state="collapsed" if hide_streamlit_ui else "auto",
)

# Apply CSS to hide sidebar immediately if not authenticated
if hide_streamlit_ui or (AUTH_ENABLED and not is_authenticated()):
    st.markdown("""
    <style>
        section[data-testid='stSidebar'] {display: none !important;}
        #MainMenu {visibility: hidden !important;}
        .stApp header {visibility: hidden !important;}
        footer {visibility: hidden !important;}
    </style>
    """, unsafe_allow_html=True)

def main():
    # Set up logging
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    
    # Load environment variables
    load_dotenv(override=True)
    logger.debug("Environment variables loaded")
    
    # Check for auth token from environment (set above)
    auth_token = os.environ.get('STREAMLIT_AUTH_TOKEN')
    if auth_token and AUTH_ENABLED:
        logger.info("Found auth token in environment, checking validity")
        # Use the token to authenticate
        if check_auth(auth_token):
            logger.info("Environment token authentication successful")
            # Remove file after successful authentication
            if os.path.exists(LOCAL_ENV_FILE):
                try:
                    os.remove(LOCAL_ENV_FILE)
                    logger.info(f"Removed {LOCAL_ENV_FILE}")
                except:
                    logger.warning(f"Failed to remove {LOCAL_ENV_FILE}")
    
    # Check authentication before proceeding
    if AUTH_ENABLED and not is_authenticated():
        logger.warning("Not authenticated, redirecting to auth service")
        redirect_to_auth()
        return
    
    # Restore normal UI after authentication
    if AUTH_ENABLED and is_authenticated():
        st.markdown("""
        <style>
            section[data-testid='stSidebar'] {display: block !important;}
            .stApp header {visibility: visible !important;}
        </style>
        """, unsafe_allow_html=True)
    
    # If we get here, user is authenticated or auth is disabled
    logger.info("User authenticated or auth disabled, proceeding to main app")
    
    # Initialize session state
    initialize_session_state()
    logger.debug("Session state initialized")
    
    # Initialize API clients if not already done
    initialize_api_clients()
    logger.debug("API clients initialization attempted")
    
    # Header and navigation
    st.image("media/microsoft.png", width=100)
    
    # Show user info and GitHub link
    header_cols = st.columns([4, 2])
    with header_cols[0]:
        st.title('Video Analysis and Chat with LLM\'s')
    
    with header_cols[1]:
        # Only show user info if authenticated
        if AUTH_ENABLED and is_authenticated():
            st.markdown(f"""
            <div style="display: flex; justify-content: flex-end; align-items: center; gap: 10px;">
                <span>👤 <b>{get_username()}</b></span>
                <span style="cursor: pointer;" onclick="window.location.href='?logout=true'">🚪 Logout</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Check for logout request
            if st.query_params.get("logout", "") == "true":
                st.query_params.clear()
                logout()
                st.rerun()
        
        # GitHub repository link
        st.markdown(
            """
            <div style="text-align: right; margin-top: 5px;">
                <a href="https://github.com/john-carroll-sw/video-analysis-with-gpt-4o" target="_blank">
                    <img src="https://img.shields.io/badge/GitHub-View%20on%20GitHub-blue?logo=github" alt="GitHub Repository"/>
                </a>
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    # Define tab titles and corresponding phases
    tabs = [
        ("Upload", "Upload"),
        ("Analyze", "Analyze"),
        ("Chat", "Chat")
    ]
    
    # Create custom tabs using columns and buttons
    cols = st.columns(len(tabs))
    
    prev_phase = st.session_state.current_phase
    
    for i, (label, phase) in enumerate(tabs):
        with cols[i]:
            button_type = "primary" if st.session_state.current_phase == phase else "secondary"
            disabled = False
            if st.button(label, key=f"tab_{i}", type=button_type, disabled=disabled, use_container_width=True):
                logger.info(f"Navigation: Switching from {prev_phase} to {phase}")
                st.session_state.current_phase = phase
                st.rerun()
    
    st.divider()  # Separator below tabs
    
    # Show the current phase
    logger.debug(f"Rendering phase: {st.session_state.current_phase}")
    if st.session_state.current_phase == "Upload":
        show_upload_page()
    elif st.session_state.current_phase == "Analyze":
        show_analyze_page()
    elif st.session_state.current_phase == "Chat":
        show_chat_page()

if __name__ == "__main__":
    main()
