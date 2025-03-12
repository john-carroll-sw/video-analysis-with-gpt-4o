import streamlit as st
import os
from dotenv import load_dotenv
import logging

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

# Configure page
st.set_page_config(
    page_title="Video Analysis and Chat with LLM's",
    layout="wide",
    initial_sidebar_state="auto",
)

def main():
    # Set up logging - will only initialize once regardless of how many times Streamlit reruns
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    
    # Load environment variables
    load_dotenv(override=True)
    logger.debug("Environment variables loaded")
    
    # Initialize session state
    initialize_session_state()
    logger.debug("Session state initialized")
    
    # Initialize API clients if not already done
    initialize_api_clients()
    logger.debug("API clients initialization attempted")
    
    # Header and navigation
    st.image("media/microsoft.png", width=100)
    st.title('Video Analysis and Chat with LLM\'s')
    
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
