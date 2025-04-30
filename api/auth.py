import os
import json
from flask import Blueprint, redirect, url_for, request, session, flash
from google_auth_oauthlib.flow import Flow

# Import constants and utils from other modules in the api package
from . import config # Import config directly
from . import utils

# Define the Blueprint
# Using url_prefix simplifies route definitions within this file
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# --- Helper Function --- 

def get_google_auth_flow():
    """Creates Google OAuth Flow.
    Attempts to load credentials from GOOGLE_CREDENTIALS_JSON environment variable first.
    Falls back to loading from CREDENTIALS_FILE if the env var is not set.
    Uses SCOPES and REDIRECT_URI from the main app config.
    """
    print("--- GET_GOOGLE_AUTH_FLOW START ---")

    # Use constants from config module
    scopes = config.SCOPES
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
            flow = Flow.from_client_config(
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
            flow = Flow.from_client_secrets_file(
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
    
    # Store original scopes from config
    original_scopes = config.SCOPES.copy()
    
    # Temporarily modify the scopes if user requested modify access
    if requested_scope == 'modify':
        print("User requested modify scope for archiving capability")
        config.SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
        # Store in session that user requested extended permissions
        session['requested_extended_permissions'] = True
        flash("You'll be asked for additional permissions to enable archiving", "info")
    else:
        # Default to read-only mode
        print("Using default read-only scope")
        session.pop('requested_extended_permissions', None)
    
    flow = get_google_auth_flow()
    if not flow:
        # Restore original scopes
        config.SCOPES = original_scopes
        flash("Could not load credentials configuration. Please check server logs.", "error")
        # Redirect to main index, not auth index
        return redirect(url_for('index'))

    print(f"[Login Route] Using Flow object: {flow}")
    print(f"[Login Route] Redirect URI from flow object: {flow.redirect_uri}")
    print(f"[Login Route] Redirect URI from config: {config.REDIRECT_URI}")
    print(f"[Login Route] Using scopes: {config.SCOPES}")

    try:
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true')
        session['oauth_state'] = state
        print(f"Generated authorization URL: {authorization_url}")
        print(f"Stored state in session: {state}")
        
        # Restore original scopes after generating the URL
        config.SCOPES = original_scopes
        
        return redirect(authorization_url)
    except Exception as e:
        # Restore original scopes
        config.SCOPES = original_scopes
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
        flow.fetch_token(authorization_response=authorization_response)
        print("--- DEBUG: oauth2callback: Token fetched successfully. ---")

        creds = flow.credentials
        utils.save_credentials(creds) # Use function from utils
        print("--- DEBUG: oauth2callback: Credentials theoretically saved to session. ---")
        session.pop('oauth_state', None)

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
    """Clears the session and logs the user out."""
    utils.clear_credentials() # Use function from utils
    flash("You have been logged out.", "info")
    return redirect(url_for('index')) 