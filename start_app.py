#!/usr/bin/env python3
import os
import sys
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("start_app")

# Load environment variables
load_dotenv(override=True)

# Check if authentication is enabled
AUTH_ENABLED = os.environ.get("VITE_AUTH_ENABLED", "false").lower() == "true"

if __name__ == "__main__":
    logger.info("Starting Video Analysis with LLMs application")
    
    # Always run through auth_server if auth is enabled
    if AUTH_ENABLED:
        logger.info("Authentication is enabled - starting HTML auth gateway")
        
        # Make sure no existing server is running on port 5555
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', 5555))
            # Port is available, close the socket
            sock.close()
        except socket.error:
            logger.warning("Port 5555 is already in use. An auth server might already be running.")
            logger.info("Attempting to continue anyway...")
        
        # Execute the auth server script in the same process
        try:
            from auth_system import main as auth_server_main
            # This will run the auth server in the main thread
            auth_server_main()
        except ImportError as e:
            logger.error(f"Failed to import auth_server module: {e}")
            sys.exit(1)
    else:
        logger.info("Authentication is disabled - starting Streamlit app directly")
        # Execute the Streamlit app directly
        import subprocess
        subprocess.run([sys.executable, "-m", "streamlit", "run", "Video_Analysis_With_LLMs.py"])

    logger.info("Application startup script completed")
