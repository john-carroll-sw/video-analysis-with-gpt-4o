import os
import http.server
import socketserver
import logging
import webbrowser
import subprocess
import sys
import time
import json
import base64
from urllib.parse import parse_qs, urlparse
from threading import Thread
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("auth_server")

# Load environment variables
load_dotenv(override=True)

# Variables
PORT = int(os.environ.get("AUTH_SERVER_PORT", "5555"))
ADDRESS = os.environ.get("AUTH_SERVER_ADDRESS", "0.0.0.0")
HTML_FILE = os.environ.get("AUTH_HTML_FILE", 'auth_landing.html')
STREAMLIT_APP = 'Video_Analysis_With_LLMs.py'
AUTH_URL = os.environ.get("VITE_AUTH_URL")
STREAMLIT_PORT = int(os.environ.get("STREAMLIT_SERVER_PORT", "8501"))
LOCAL_ENV_FILE = ".streamlit_auth_env"
FRONTEND_URL = os.environ.get("FRONTEND_URL", f"http://localhost:{PORT}")

# For Azure deployment, determine the app's URL for redirects
IS_AZURE = os.environ.get("WEBSITE_HOSTNAME") is not None
APP_URL = f"https://{os.environ.get('WEBSITE_HOSTNAME')}" if IS_AZURE else f"http://localhost:{STREAMLIT_PORT}"

# Global streamlit process reference
streamlit_process = None

class AuthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests, particularly for authentication callbacks"""
        logger.info(f"Received GET request: {self.path}")
        
        # Parse the URL and query parameters
        parsed_url = urlparse(self.path)
        
        # Handle root path - serve the landing page
        if parsed_url.path == '/':
            self.serve_landing_page()
            return
            
        # Handle authentication callback with token
        if parsed_url.path.startswith('/callback'):
            query_params = parse_qs(parsed_url.query)
            token = query_params.get('t', [None])[0]
            
            if token:
                logger.info("Received authentication token in callback")
                
                # Write token to file for Streamlit to read
                with open(LOCAL_ENV_FILE, 'w') as f:
                    f.write(f"AUTH_TOKEN={token}\n")
                
                # Only start Streamlit after authentication is successful in local dev
                global streamlit_process
                if not IS_AZURE and (not streamlit_process or streamlit_process.poll() is not None):
                    logger.info("Starting Streamlit app after successful authentication")
                    start_streamlit_in_background()
                
                # Show a success page that redirects to the appropriate app URL
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                redirect_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta http-equiv="refresh" content="1;URL='{APP_URL}'">
                    <title>Authentication Successful</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                        .success {{ color: green; }}
                        .spinner {{ 
                            border: 5px solid #f3f3f3;
                            border-top: 5px solid #3498db;
                            border-radius: 50%;
                            width: 50px;
                            height: 50px;
                            animation: spin 1s linear infinite;
                            margin: 20px auto;
                        }}
                        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                    </style>
                </head>
                <body>
                    <h2 class="success">Authentication Successful!</h2>
                    <p>Starting Video Analysis application...</p>
                    <div class="spinner"></div>
                    <p>You will be redirected automatically to {APP_URL}</p>
                </body>
                </html>
                """
                self.wfile.write(redirect_html.encode('utf-8'))
                return
        
        # Serve files normally for other paths
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def serve_landing_page(self):
        """Serve the authentication landing page"""
        # Check if user is already authenticated (token exists and is valid)
        token_path = LOCAL_ENV_FILE
        if os.path.exists(token_path):
            with open(token_path, 'r') as f:
                content = f.read()
                if content.startswith('AUTH_TOKEN='):
                    token = content[11:].strip()
                    if self.validate_token(token):
                        # Start Streamlit if it's not already running and in dev mode
                        global streamlit_process
                        if not IS_AZURE and (not streamlit_process or streamlit_process.poll() is not None):
                            logger.info("Starting Streamlit app with existing token")
                            start_streamlit_in_background()
                            
                        # Show redirect page
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        
                        redirect_html = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta http-equiv="refresh" content="0;URL='{APP_URL}'">
                            <title>Redirecting...</title>
                        </head>
                        <body>
                            <p>Redirecting to application at {APP_URL}...</p>
                        </body>
                        </html>
                        """
                        self.wfile.write(redirect_html.encode('utf-8'))
                        return
        
        # Serve the landing page
        try:
            with open(HTML_FILE, 'rb') as file:
                content = file.read()
                
                # Add customized JavaScript with correct endpoint and port info
                app_info_script = f"""
                <script>
                const AUTH_URL = "{AUTH_URL}";
                const FRONTEND_URL = "{FRONTEND_URL}";
                const CALLBACK_URL = "{FRONTEND_URL}/callback";
                
                // Custom login code
                function loginToApp() {{
                    // Prepare app info for authentication
                    const info = {{
                        app: 'Video Analysis with LLMs',
                        url: CALLBACK_URL
                    }};
                    
                    // Encode the info
                    const encodedInfo = btoa(JSON.stringify(info));
                    
                    // Show loading indicator
                    document.getElementById('loadingIndicator').style.display = 'block';
                    
                    // Redirect to authentication service
                    window.location.href = AUTH_URL + '/signin/?v=' + encodedInfo;
                }}
                
                // Auto-redirect on page load
                document.addEventListener('DOMContentLoaded', function() {{
                    // Delay slightly to ensure page content is visible first
                    setTimeout(loginToApp, 800);
                    
                    // Also connect login button
                    document.getElementById('loginButton').addEventListener('click', function() {{
                        document.getElementById('loadingIndicator').style.display = 'block';
                        loginToApp();
                    }});
                }});
                </script>
                """
                
                # Insert custom script before closing </body> tag
                content_str = content.decode('utf-8')
                content_str = content_str.replace('</body>', f'{app_info_script}</body>')
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(content_str.encode('utf-8'))
                
        except FileNotFoundError:
            self.send_error(404, f"File {HTML_FILE} not found")
    
    def validate_token(self, token):
        """Validate the authentication token"""
        try:
            token_data = json.loads(base64.b64decode(token))
            if 'expiry' in token_data:
                # Check if token is not expired
                if time.time() * 1000 < token_data.get('expiry', 0):
                    return True
            return False
        except:
            return False
    
    def log_message(self, format, *args):
        # Override to use our logger
        logger.info("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

def start_streamlit_in_background():
    """Start the Streamlit app in the background"""
    global streamlit_process
    
    # Make sure any existing process is terminated
    if streamlit_process and streamlit_process.poll() is None:
        try:
            streamlit_process.terminate()
            time.sleep(1)  # Give it time to terminate
        except:
            pass
    
    # Check if we're running in a virtual environment
    venv_python = None
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        if os.name == 'nt':  # Windows
            venv_python = os.path.join(sys.prefix, 'Scripts', 'python')
        else:  # Unix-like
            venv_python = os.path.join(sys.prefix, 'bin', 'python')
    
    # Build the command
    cmd = []
    if venv_python and os.path.exists(venv_python):
        cmd = [venv_python, '-m', 'streamlit', 'run', STREAMLIT_APP]
    else:
        cmd = [sys.executable, '-m', 'streamlit', 'run', STREAMLIT_APP]
    
    # Add environment variables
    env = os.environ.copy()
    env['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'  # Disable usage stats
    env['STREAMLIT_SERVER_HEADLESS'] = 'true'  # Prevent auto-opening browser
    env['STREAMLIT_THEME_BACKGROUND_COLOR'] = '#FFFFFF'  # Set background color
    
    # Start Streamlit process in the background
    logger.info(f"Launching Streamlit with: {' '.join(cmd)}")
    streamlit_process = subprocess.Popen(cmd, env=env)
    
    # Give Streamlit time to start up
    time.sleep(3)

def start_http_server():
    """Start the authentication gateway server"""
    try:
        with socketserver.TCPServer((ADDRESS, PORT), AuthHandler) as httpd:
            logger.info(f"Authentication gateway serving at http://{ADDRESS}:{PORT}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("HTTP Server stopped.")
        # Terminate Streamlit process if running
        global streamlit_process
        if streamlit_process and streamlit_process.poll() is None:
            streamlit_process.terminate()
    except Exception as e:
        logger.error(f"HTTP Server error: {str(e)}")

def main():
    """Main function to start the authentication server."""
    logger.info("Starting authentication gateway")
    
    # Check if HTML file exists
    if not os.path.exists(HTML_FILE):
        logger.error(f"HTML file {HTML_FILE} not found in the current directory.")
        return
    
    # Start HTTP server in the main thread
    try:
        logger.info(f"Starting authentication server on port {PORT}")
        # Open browser to the landing page
        webbrowser.open(f'http://{ADDRESS}:{PORT}')
        
        # Start HTTP server in main thread
        start_http_server()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
        # Make sure to terminate any running Streamlit process
        if streamlit_process and streamlit_process.poll() is None:
            streamlit_process.terminate()

if __name__ == "__main__":
    main()
