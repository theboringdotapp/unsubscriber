import os
import json
import functions_framework
from flask import jsonify, redirect, request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from flask_cors import CORS
import google.auth.transport.requests

# Environment variables (can be set in deployment platform)
CLIENT_SECRET_FILE = os.environ.get('CLIENT_SECRET_FILE', 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']  # Read, modify, send

# This will be your frontend URL
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5000')

# Needed to make auth work in a serverless context
# You'll need to use these same values in your frontend
STATE_SECRET = os.environ.get('STATE_SECRET', 'serverless-gmail-unsub')

@functions_framework.http
def auth_handler(request):
    """Handle all authentication-related requests."""
    # Enable CORS for all routes
    if request.method == 'OPTIONS':
        # Handle preflight request
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }

    path = request.path
    
    # Routing based on the path after /api/auth
    if request.path.endswith('/login'):
        response = handle_login(request)
        return (response[0], response[1], {**headers, **response[2]} if len(response) > 2 else headers)
    elif request.path.endswith('/callback'):
        response = handle_callback(request)
        return (response[0], response[1], {**headers, **response[2]} if len(response) > 2 else headers)
    elif request.path.endswith('/refresh'):
        response = handle_refresh(request)
        return (response[0], response[1], {**headers, **response[2]} if len(response) > 2 else headers)
    else:
        return (jsonify({'error': 'Unknown endpoint'}), 404, headers)

def handle_login(request):
    """Start the OAuth flow."""
    try:
        # Create the flow instance
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=request.url_root + 'callback'  # This should be the full URL to your callback endpoint
        )
        
        # Generate URL for request to Google's OAuth 2.0 server
        authorization_url, state = flow.authorization_url(
            # Enable offline access to refresh token
            access_type='offline',
            # Force approval to always get a refresh token
            prompt='consent',
            # Custom state to validate on callback
            state=STATE_SECRET
        )
        
        # Redirect to authorization URL
        return redirect(authorization_url), 302, {}
    except Exception as e:
        return jsonify({'error': str(e)}), 500, {}

def handle_callback(request):
    """Handle the OAuth callback."""
    try:
        # Verify state parameter
        state = request.args.get('state', '')
        if state != STATE_SECRET:
            return jsonify({'error': 'Invalid state parameter'}), 400, {}
        
        # Get authorization code and exchange for tokens
        code = request.args.get('code', '')
        if not code:
            return jsonify({'error': 'Authorization code not found'}), 400, {}
            
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=request.url_root + 'callback'
        )
        
        # Exchange code for tokens
        flow.fetch_token(code=code)
        
        # Get credentials from flow
        credentials = flow.credentials
        
        # Create a serializable version of credentials
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Redirect back to frontend with token data in fragment (hash)
        # The frontend will parse this data from the URL fragment
        token_param = f"#token={json.dumps(token_data)}"
        redirect_url = f"{FRONTEND_URL}{token_param}"
        
        return redirect(redirect_url), 302, {}
    except Exception as e:
        # Redirect back to frontend with error
        error_param = f"#error={str(e)}"
        redirect_url = f"{FRONTEND_URL}{error_param}"
        return redirect(redirect_url), 302, {}

def handle_refresh(request):
    """Refresh the access token."""
    try:
        # Get token data from request
        token_data = json.loads(request.get_data().decode('utf-8'))
        
        # Create credentials from token data
        credentials = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes')
        )
        
        # Refresh the token
        request_adapter = google.auth.transport.requests.Request()
        credentials.refresh(request_adapter)
        
        # Create updated token data
        updated_token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        return jsonify(updated_token_data), 200, {}
    except Exception as e:
        return jsonify({'error': str(e)}), 500, {} 