import streamlit as st
import requests
import base64
import json
import time
import os
import logging
from urllib.parse import urlencode, quote
from dotenv import load_dotenv

# Set up logger
logger = logging.getLogger('custom_auth')

# Load environment variables
load_dotenv(override=True)

# Get authentication URL from environment
AUTH_URL = os.environ.get("VITE_AUTH_URL", "")
AUTH_ENABLED = os.environ.get("VITE_AUTH_ENABLED", "false").lower() == "true"

def initialize_auth():
    """Initialize authentication state variables if they don't exist."""
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None
    if "auth_expiry" not in st.session_state:
        st.session_state.auth_expiry = 0
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False

def encode_info():
    """Create encoded app info similar to React implementation."""
    info = {
        'app': 'Video Analysis with LLMs',
        'url': os.environ.get('FRONTEND_URL', 'http://localhost:8501')
    }
    encoded = base64.b64encode(json.dumps(info).encode()).decode()
    return encoded

def redirect_to_auth():
    """Create a signin URL and redirect user to authentication service."""
    encoded_info = encode_info()
    signin_url = f"{AUTH_URL}/signin/?v={encoded_info}"
    
    # Use more robust redirection approach with JavaScript
    st.markdown(f"""
    <meta http-equiv="refresh" content="0;URL='{signin_url}'" />
    <script>
        window.location.href = "{signin_url}";
    </script>
    <p>If you are not redirected automatically, <a href="{signin_url}">click here</a>.</p>
    """, unsafe_allow_html=True)
    
    # Stop execution after redirect
    st.stop()

def parse_token_from_url():
    """Check if there's a token in the URL parameters."""
    # Get query parameters using the updated API
    token = st.query_params.get("t", None)
    
    if token:
        logger.info("Found token in URL parameters")
        # Remove token from URL to prevent issues on refresh
        st.query_params.clear()
        return token
    
    return None

def check_auth(token):
    """Verify if the token is valid by calling the authentication API."""
    if not token:
        return False
    
    try:
        # Decode token to get expiry
        token_data = json.loads(base64.b64decode(token))
        
        # Check if token is expired
        if time.time() * 1000 > token_data.get('expiry', 0):
            logger.info("Token expired, verifying with API")
            
            # Call API to check if token is still valid
            response = requests.get(
                f"{AUTH_URL}/auth/check/",
                headers={"x-token": token_data.get('token', '')},
                timeout=10
            )
            
            if not response.ok:
                logger.warning("API auth check failed")
                return False
            
            logger.info("API auth check successful")
            
            # Update token in session state
            st.session_state.auth_token = token
            st.session_state.auth_user = token_data.get('user', {})
            st.session_state.auth_expiry = token_data.get('expiry', 0)
            st.session_state.is_authenticated = True
            return True
        else:
            logger.info("Token still valid")
            
            # Store token info in session state
            st.session_state.auth_token = token
            st.session_state.auth_user = token_data.get('user', {})
            st.session_state.auth_expiry = token_data.get('expiry', 0)
            st.session_state.is_authenticated = True
            return True
    
    except Exception as e:
        logger.error(f"Auth check error: {str(e)}")
        return False

def is_authenticated():
    """Check if the user is authenticated."""
    # Initialize auth state variables if necessary
    initialize_auth()
    
    # First check for token in URL
    token_from_url = parse_token_from_url()
    if token_from_url and check_auth(token_from_url):
        logger.info("Authentication successful with URL token")
        return True
    
    # If no URL token or it's invalid, check session state
    if st.session_state.auth_token and check_auth(st.session_state.auth_token):
        logger.info("Authentication successful with session token")
        return True
    
    logger.info("Authentication failed - no valid token found")
    return False

def handle_auth():
    """
    Main authentication handler - to be called at app startup.
    Returns True if authenticated or auth not enabled, False otherwise.
    """
    # If auth is not enabled, skip authentication
    if not AUTH_ENABLED:
        return True
    
    return is_authenticated()

def logout():
    """Log out the current user and clear auth state."""
    logger.info("Logging out user")
    st.session_state.auth_token = None
    st.session_state.auth_user = None
    st.session_state.auth_expiry = 0
    st.session_state.is_authenticated = False
    
    # Clear all session state to fully reset the app
    for key in list(st.session_state.keys()):
        if key != "auth_token" and key != "auth_user" and key != "auth_expiry" and key != "is_authenticated":
            del st.session_state[key]
    
    # Redirect to signin page
    redirect_to_auth()

def get_username():
    """Get the current user's name if authenticated."""
    if st.session_state.auth_user and 'name' in st.session_state.auth_user:
        return st.session_state.auth_user['name']
    return "User"
