import os
import json
from flask import Blueprint, redirect, url_for, request, session, flash
from google_auth_oauthlib.flow import Flow

# Import constants and utils from other modules in the api package
from . import config # Import config directly
from . import utils
from .oauth_helper import NoScopeValidationFlow

# Define the Blueprint
# Using url_prefix simplifies route definitions within this file
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# --- Helper Function --- 

def get_google_auth_flow():
    """Creates Google OAuth Flow.
    Attempts to load credentials from GOOGLE_CREDENTIALS_JSON environment variable first.
    Falls back to loading from CREDENTIALS_FILE if the env var is not set.
    Uses SCOPES from session if available or from config as fallback.
    """
    print("--- GET_GOOGLE_AUTH_FLOW START ---")

    # Use scopes from session if they're available, otherwise use config scopes
    scopes = session.get('requested_scopes', config.SCOPES)
    print(f"Using scopes: {scopes}")
    
    redirect_uri = config.REDIRECT_URI
    credentials_file = config.CREDENTIALS_FILE

    credentials_json_content = os.environ.get('GOOGLE_CREDENTIALS_JSON')

    if credentials_json_content:
        print("Loading credentials from GOOGLE_CREDENTIALS_JSON environment variable.")
        try:
            client_config = json.loads(credentials_json_content)
            if 'web' not in client_config and 'installed' not in client_config:
                 print("!!! ERROR: GOOGLE_CREDENTIALS_JSON does not contain 'web' or 'installed' key. !!!")
                 return None
            flow = NoScopeValidationFlow.from_client_config(
                client_config,
                scopes=scopes,
                redirect_uri=redirect_uri)
            print("Successfully created Flow object from environment variable.")
            print("--- GET_GOOGLE_AUTH_FLOW END ---")
            return flow
        except json.JSONDecodeError as e:
             print(f"!!! ERROR: Failed to parse JSON from GOOGLE_CREDENTIALS_JSON: {e} !!!")
             return None
        except Exception as e:
            print(f"!!! ERROR creating Flow from environment variable config: {e} !!!")
            return None
    else:
        print("GOOGLE_CREDENTIALS_JSON not found. Falling back to credentials file.")
        # Construct path relative to project root (assuming index.py is at root)
        # This might need adjustment depending on final structure
        # Using absolute path from index.project_root might be safer
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # api -> project root
        abs_credentials_file = os.path.join(project_root, credentials_file) 
        print(f"Attempting to load credentials from file: {abs_credentials_file}")

        if not os.path.exists(abs_credentials_file):
            print(f"!!! ERROR: {abs_credentials_file} not found! Ensure '{credentials_file}' is in the project root OR set GOOGLE_CREDENTIALS_JSON env var. !!!")
            return None

        try:
            flow = NoScopeValidationFlow.from_client_secrets_file(
                abs_credentials_file,
                scopes=scopes,
                redirect_uri=redirect_uri)
            print(f"Successfully created Flow object from file.")
            print("--- GET_GOOGLE_AUTH_FLOW END ---")
            return flow
        except Exception as e:
            print(f"!!! ERROR in get_google_auth_flow loading/parsing {abs_credentials_file}: {e} !!!")
            return None

# --- Routes --- 

# Note: Routes defined with auth_bp use the /auth prefix automatically
# e.g., this becomes /auth/login
@auth_bp.route('/login')
def login():
    """Initiates the Google OAuth flow."""
    utils.clear_credentials()
    print("Starting login flow, cleared session credentials.")
    
    # Check if the user requested extended permissions
    requested_scope = request.args.get('scope')
    
    # Initialize with default scopes
    requested_scopes = config.SCOPES.copy()
    
    # Update to modify scope if requested
    if requested_scope == 'modify':
        print("User requested modify scope for archiving capability")
        # Request both scopes to avoid permission errors during scope change
        requested_scopes = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.readonly']
        # Store in session that user requested extended permissions
        session['requested_extended_permissions'] = True
        session['requested_scopes'] = requested_scopes
        flash("You'll be asked for additional permissions to enable archiving", "info")
    else:
        # Default to read-only mode
        print("Using default read-only scope")
        session.pop('requested_extended_permissions', None)
        session.pop('requested_scopes', None)
    
    # Store requested scopes in session for the flow to use
    session['requested_scopes'] = requested_scopes
    
    # Create flow with the requested scopes (flow will get scopes from session)
    flow = get_google_auth_flow()
    
    if not flow:
        flash("Could not load credentials configuration. Please check server logs.", "error")
        # Redirect to main index, not auth index
        return redirect(url_for('index'))

    print(f"[Login Route] Using Flow object: {flow}")
    print(f"[Login Route] Redirect URI from flow object: {flow.redirect_uri}")
    print(f"[Login Route] Redirect URI from config: {config.REDIRECT_URI}")
    print(f"[Login Route] Using scopes: {session.get('requested_scopes') or config.SCOPES}")

    try:
        # Make sure we capture the actual scopes being used for this flow
        print(f"Using scopes for authorization: {session.get('requested_scopes', config.SCOPES)}")
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true')
        session['oauth_state'] = state
        print(f"Generated authorization URL: {authorization_url}")
        print(f"Stored state in session: {state}")
        
        return redirect(authorization_url)
    except Exception as e:
        flash(f"Error generating authorization URL: {e}", "error")
        print(f"Error generating authorization URL: {e}")
        return redirect(url_for('index'))

# This becomes /auth/oauth2callback implicitly because it's defined in index.py
# We need to redefine it here under the blueprint, maybe without prefix?
# Or adjust the REDIRECT_URI to include /auth. 
# Let's keep REDIRECT_URI as /oauth2callback and define this route at the app level or adjust REDIRECT_URI.
# Easier: Adjust REDIRECT_URI in index.py to be BASE_URL + /auth/oauth2callback
# and define this route under the blueprint.
@auth_bp.route('/oauth2callback') 
def oauth2callback():
    """Handles the OAuth callback from Google."""
    print("--- OAUTH2CALLBACK START ---")
    state = session.get('oauth_state')
    print(f"Session state: {state}")
    print(f"Request args: {request.args}")

    # Check for the 'handled' flag to prevent redirect loops
    handled = request.args.get('handled')
    if not handled:
        # Redirect to intermediary page that will handle the callback
        print("First OAuth callback hit - redirecting to intermediary page to prevent loops")
        query_string = request.query_string.decode('utf-8')
        
        # Clear credentials but NOT the oauth_state
        utils.clear_credentials()
        session.pop('current_auth_scopes', None)
        # Keep both requested_scopes and oauth_state to ensure the flow works
        print("Cleared old credentials before completing flow (preserving oauth_state)")
        
        return redirect(f'/oauth2callback?{query_string}&handled=true')

    error = request.args.get('error')
    if error:
        flash(f"Authentication failed: {error}", "error")
        print(f"OAuth callback error: {error}")
        return redirect(url_for('index'))

    request_state = request.args.get('state')
    if not state or state != request_state:
        flash("State mismatch during authentication. Please try again.", "error")
        print(f"State mismatch: session='{state}', request='{request_state}'")
        return redirect(url_for('.login')) # Use relative blueprint redirect

    flow = get_google_auth_flow()
    if not flow:
         flash("Could not load credentials configuration after callback. Check logs.", "error")
         print("get_google_auth_flow returned None during callback.")
         return redirect(url_for('index'))

    try:
        # Log the scopes that the flow is using - this is crucial for debugging
        print(f"--- DEBUG: OAuth callback using flow with scopes: {flow.oauth2session.scope} ---")
        
        authorization_response = request.url
        
        # Use BASE_URL from config 
        base_url = config.BASE_URL 
        if base_url.startswith('http://') and ('127.0.0.1' in base_url or 'localhost' in base_url):
            forwarded_proto = request.headers.get('x-forwarded-proto')
            if forwarded_proto == 'https':
                 print("--- DEBUG: oauth2callback: Detected x-forwarded-proto=https, using original request.url ---")
            else:
                 print("--- DEBUG: oauth2callback: Local HTTP detected. Replacing http:// with https:// for Google check. ---")
                 authorization_response = authorization_response.replace('http://', 'https://', 1)

        print(f"--- DEBUG: oauth2callback: Fetching token with authorization_response: {authorization_response} ---")
        # Don't validate scope changes to avoid errors on upgrade
        flow.fetch_token(authorization_response=authorization_response)
        print("--- DEBUG: oauth2callback: Token fetched successfully. ---")

        creds = flow.credentials
        print(f"--- DEBUG: oauth2callback: Credentials scopes: {creds.scopes} ---")
        
        # Ensure we have the needed scopes
        modify_scope = 'https://www.googleapis.com/auth/gmail.modify'
        readonly_scope = 'https://www.googleapis.com/auth/gmail.readonly'
        requested_extended_permissions = session.get('requested_extended_permissions', False)
        
        # Log the current situation
        print(f"--- DEBUG: oauth2callback: Extended permissions requested: {requested_extended_permissions} ---")
        print(f"--- DEBUG: oauth2callback: Checking if creds have required scopes ---")
        
        if requested_extended_permissions and modify_scope not in creds.scopes:
            print(f"--- ERROR: oauth2callback: Modify scope was requested but not granted! ---")
            flash("The requested permissions were not granted. Please try again.", "error")
            return redirect(url_for('.login'))
            
        # Save credentials and clear session data
        utils.save_credentials(creds) # Use function from utils
        print("--- DEBUG: oauth2callback: Credentials theoretically saved to session. ---")
        
        # Clear all OAuth-related session data to prevent stale state
        session.pop('oauth_state', None)
        session.pop('requested_scopes', None)
        session.pop('current_auth_scopes', None)

        # If this was an archive permission upgrade, redirect back to scan page with the token
        requested_extended_permissions = session.get('requested_extended_permissions', False)
        return_to_scan = session.get('return_to_scan_token')
        
        if requested_extended_permissions and return_to_scan:
            flash("Archive permission successfully enabled!", "success")
            print(f"--- OAUTH2CALLBACK END (SUCCESS) - Redirecting back to scan with token: {return_to_scan} ---")
            # Clear the return token from session
            session.pop('return_to_scan_token', None)
            return redirect(url_for('scan.scan_emails', token=return_to_scan, archive_enabled='true'))
        else:
            flash("Authentication successful!", "success")
            print("--- OAUTH2CALLBACK END (SUCCESS) ---")
            return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error fetching token or saving credentials: {e}", "error")
        print(f"!!! ERROR in oauth2callback during token fetch/save: {e} !!!")
        utils.clear_credentials() # Use function from utils
        print("--- OAUTH2CALLBACK END (ERROR) ---")
        return redirect(url_for('.login')) # Use relative blueprint redirect


@auth_bp.route('/logout')
def logout():
    """Clears the session and logs the user out completely."""
    # First, clear credentials
    utils.clear_credentials()
    
    # Clear all OAuth-related session data
    session.pop('oauth_state', None)
    session.pop('requested_scopes', None)
    session.pop('requested_extended_permissions', None)
    session.pop('current_auth_scopes', None)
    session.pop('return_to_scan_token', None)
    
    # Clear any other session data
    session.clear()
    
    # Create a response with cache-control headers to clear browser cache
    response = redirect(url_for('index'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Create HTML with logout script to clear browser storage before redirect
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logging out...</title>
        <script>
            // Clear all localStorage
            localStorage.clear();
            
            // Clear all sessionStorage
            sessionStorage.clear();
            
            // Clear cookies
            document.cookie.split(';').forEach(function(c) {
                document.cookie = c.trim().split('=')[0] + '=;' + 'expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/';
            });
            
            // Show message
            document.addEventListener('DOMContentLoaded', function() {
                document.getElementById('message').textContent = 'You have been logged out. Redirecting...';
            });
            
            // Redirect to homepage after a short delay
            setTimeout(function() {
                window.location.href = '/';
            }, 1000);
        </script>
    </head>
    <body style="font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f5f5f5;">
        <div style="text-align: center; padding: 2rem; background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h2>Logging out</h2>
            <p id="message">Clearing data...</p>
        </div>
    </body>
    </html>
    """
    
    return html