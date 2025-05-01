import os
import json
from flask import Blueprint, redirect, url_for, request, session, flash, get_flashed_messages
from google_auth_oauthlib.flow import Flow

# Import constants and utils from other modules in the api package
from . import config # Import config directly
from . import utils

# Define the Blueprint
# Using url_prefix simplifies route definitions within this file
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# --- Helper Function --- 

def get_google_auth_flow(scopes_list=None):
    """Creates Google OAuth Flow.
    Attempts to load credentials from GOOGLE_CREDENTIALS_JSON environment variable first.
    Falls back to loading from CREDENTIALS_FILE if the env var is not set.
    Uses provided scopes or SCOPES from config as fallback.
    """
    if utils.should_log(): print("--- GET_GOOGLE_AUTH_FLOW START ---")

    # Use provided scopes or fallback to config scopes
    scopes_to_use = scopes_list if scopes_list else config.SCOPES
    if utils.should_log(): print(f"Using scopes: {scopes_to_use}")
    
    redirect_uri = config.REDIRECT_URI
    credentials_file = config.CREDENTIALS_FILE

    credentials_json_content = os.environ.get('GOOGLE_CREDENTIALS_JSON')

    if credentials_json_content:
        if utils.should_log(): print("Loading credentials from GOOGLE_CREDENTIALS_JSON environment variable.")
        try:
            client_config = json.loads(credentials_json_content)
            if 'web' not in client_config and 'installed' not in client_config:
                 print("!!! ERROR: GOOGLE_CREDENTIALS_JSON does not contain 'web' or 'installed' key. !!!")
                 return None
            # Use standard Flow
            flow = Flow.from_client_config(
                client_config,
                scopes=scopes_to_use,
                redirect_uri=redirect_uri)
            if utils.should_log(): print("Successfully created Flow object from environment variable.")
            if utils.should_log(): print("--- GET_GOOGLE_AUTH_FLOW END ---")
            return flow
        except json.JSONDecodeError as e:
             print(f"!!! ERROR: Failed to parse JSON from GOOGLE_CREDENTIALS_JSON: {e} !!!")
             return None
        except Exception as e:
            print(f"!!! ERROR creating Flow from environment variable config: {e} !!!")
            return None
    else:
        if utils.should_log(): print("GOOGLE_CREDENTIALS_JSON not found. Falling back to credentials file.")
        # Construct path relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # api -> project root
        abs_credentials_file = os.path.join(project_root, credentials_file) 
        if utils.should_log(): print(f"Attempting to load credentials from file: {abs_credentials_file}")

        if not os.path.exists(abs_credentials_file):
            print(f"!!! ERROR: {abs_credentials_file} not found! Ensure '{credentials_file}' is in the project root OR set GOOGLE_CREDENTIALS_JSON env var. !!!")
            return None

        try:
            # Use standard Flow
            flow = Flow.from_client_secrets_file(
                abs_credentials_file,
                scopes=scopes_to_use,
                redirect_uri=redirect_uri)
            if utils.should_log(): print(f"Successfully created Flow object from file.")
            if utils.should_log(): print("--- GET_GOOGLE_AUTH_FLOW END ---")
            return flow
        except Exception as e:
            print(f"!!! ERROR in get_google_auth_flow loading/parsing {abs_credentials_file}: {e} !!!")
            return None

# --- Routes --- 

@auth_bp.route('/login')
def login():
    """Initiates the Google OAuth flow. Handles initial login and permission upgrades."""
    # --- Check if already authenticated AND not requesting scope upgrade ---
    service = utils.get_gmail_service()
    requested_scope_type = request.args.get('scope') # Get scope early
    if service and requested_scope_type != 'modify':
        if utils.should_log(): print(f"User already authenticated (scopes: {service.credentials.scopes if service.credentials else 'N/A'}) and not requesting modify scope. Redirecting to dashboard.")
        return redirect('/dashboard')
    # --- End check ---
    
    # If not authenticated OR requesting modify scope, proceed with login flow
    # Clear creds only if it's a fresh login, not a scope upgrade for an existing session?
    # Let's keep clear_credentials for simplicity for now, Google handles re-consent.
    utils.clear_credentials() 
    session.pop('oauth_state', None) 
    session.pop('post_auth_redirect', None)
    if utils.should_log(): print("Proceeding with OAuth flow (New Login or Scope Upgrade)...")

    # requested_scope_type = request.args.get('scope') # Moved up
    return_to_url = request.args.get('return_to', request.referrer) 

    # --- Scope Determination Logic --- #
    if requested_scope_type == 'modify':
        if utils.should_log(): print("User requested modify scope for archiving capability")
        scopes_for_flow = [
            'https://www.googleapis.com/auth/gmail.modify', 
            'https://www.googleapis.com/auth/gmail.readonly'
        ]
        # Store return URL for redirecting back after permissions granted
        if return_to_url:
            session['post_auth_redirect'] = return_to_url
            if utils.should_log(): print(f"Stored post-auth redirect URL: {return_to_url}")
        flash("Requesting additional permissions for archiving.", "info")
    else:
        if utils.should_log(): print("Using default read-only scope")
        scopes_for_flow = config.SCOPES.copy()
    # --- End Scope Determination --- #
    
    # Store the scopes we are about to request in the session
    session['oauth_request_scopes'] = scopes_for_flow
    if utils.should_log(): print(f"Stored oauth_request_scopes in session: {scopes_for_flow}")
    
    # Create flow with the determined scopes
    flow = get_google_auth_flow(scopes_list=scopes_for_flow)
    
    if not flow:
        flash("Could not load credentials configuration. Please check server logs.", "error")
        return redirect('/') # Redirect to static home page on error

    if utils.should_log():
        print(f"[Login Route] Using Flow with scopes: {scopes_for_flow}")
        print(f"[Login Route] Redirect URI: {flow.redirect_uri}")

    try:
        # Always use prompt='consent' to ensure user sees the consent screen
        # This is crucial for handling scope changes
        authorization_url, state = flow.authorization_url(
            access_type='offline', # Request refresh token
            prompt='consent',  # Force the consent screen every time
            include_granted_scopes='true'
        )
        session['oauth_state'] = state # Store state for verification in callback
        if utils.should_log():
            print(f"Generated authorization URL: {authorization_url}")
            print(f"Stored state in session: {state}")
        
        return redirect(authorization_url)
    except Exception as e:
        flash(f"Error generating authorization URL: {e}", "error")
        print(f"Error generating authorization URL: {e}")
        return redirect('/') # Redirect to static home page on error


@auth_bp.route('/oauth2callback') 
def oauth2callback():
    """Handles the OAuth callback from Google after user authorization."""
    if utils.should_log(): print("--- OAUTH2CALLBACK START ---")
    # Consume any existing flash messages to prevent duplicates
    _ = get_flashed_messages()

    state = session.get('oauth_state')
    if utils.should_log():
        print(f"Session state: {state}")
        print(f"Request args: {request.args}")

    # Remove the intermediate page logic ('handled' check is gone)

    error = request.args.get('error')
    if error:
        flash(f"Authentication failed: {error}", "error")
        print(f"OAuth callback error: {error}")
        # Clear state if error occurs
        session.pop('oauth_state', None)
        session.pop('post_auth_redirect', None)
        return redirect('/') # Redirect to static home page on error

    request_state = request.args.get('state')
    if not state or state != request_state:
        flash("State mismatch during authentication. Please try logging in again.", "error")
        print(f"State mismatch: session='{state}', request='{request_state}'")
        # Clear state on mismatch
        session.pop('oauth_state', None)
        session.pop('post_auth_redirect', None)
        return redirect(url_for('.login')) # Use relative blueprint redirect to login

    # State is valid, clear it now as it's single-use
    session.pop('oauth_state', None)

    # Retrieve the scopes that were used for the initial auth request
    expected_scopes = session.pop('oauth_request_scopes', config.SCOPES) # Fallback needed?
    if utils.should_log(): print(f"Retrieved expected scopes from session: {expected_scopes}")

    # Recreate the flow using the scopes that were originally requested
    flow = get_google_auth_flow(scopes_list=expected_scopes)
    if not flow:
         flash("Could not load credentials configuration after callback. Check logs.", "error")
         print("get_google_auth_flow returned None during callback.")
         session.pop('post_auth_redirect', None) # Clear redirect target on error
         return redirect('/') # Redirect to static home page on error

    try:
        authorization_response = request.url
        # Handle http vs https for local development if necessary (though Vercel often handles this)
        # The original https replacement logic might still be useful if running locally *not* via `vercel dev`
        base_url = config.BASE_URL 
        if base_url.startswith('http://') and ('127.0.0.1' in base_url or 'localhost' in base_url):
             # Check for reverse proxy header common in cloud environments
            forwarded_proto = request.headers.get('x-forwarded-proto')
            if forwarded_proto == 'https':
                 if utils.should_log(): print("--- DEBUG: oauth2callback: Detected x-forwarded-proto=https, using original request.url ---")
            elif not request.url.startswith('https'):
                 if utils.should_log(): print("--- DEBUG: oauth2callback: Local HTTP detected, and no https proxy header. Replacing http:// with https:// for Google check. ---")
                 authorization_response = authorization_response.replace('http://', 'https://', 1)

        if utils.should_log(): print(f"--- DEBUG: oauth2callback: Fetching token with authorization_response: {authorization_response} ---")

        # Fetch the token using the authorization response URL
        flow.fetch_token(authorization_response=authorization_response)
        if utils.should_log(): print("--- DEBUG: oauth2callback: Token fetched successfully. ---")

        creds = flow.credentials
        if utils.should_log(): print(f"--- DEBUG: oauth2callback: Credentials obtained with scopes: {creds.scopes} ---")

        # Save the obtained credentials to the session
        utils.save_credentials(creds)
        if utils.should_log(): print(f"--- DEBUG: oauth2callback: Credentials saved. Scopes in saved creds: {creds.scopes} ---")

        # Determine redirect target
        redirect_url = session.pop('post_auth_redirect', None) # Get stored URL if it exists

        if redirect_url:
            flash("Permissions updated successfully!", "success")
            if utils.should_log(): print(f"--- OAUTH2CALLBACK END (SUCCESS - UPGRADE) - Redirecting back to: {redirect_url} ---")
            # Append a parameter to indicate success or modify state if needed by the target page
            # Example: redirect_url += "?archive_enabled=true"
            # This depends on how the target page consumes this info.
            # For simplicity, just redirecting for now.
            return redirect(redirect_url)
        else:
            flash("Authentication successful!", "success")
            if utils.should_log(): print("--- OAUTH2CALLBACK END (SUCCESS - LOGIN) - Redirecting to /dashboard ---")
            return redirect('/dashboard') # Default redirect to dashboard

    except Exception as e:
        flash(f"Error processing authentication callback: {e}", "error")
        print(f"!!! ERROR in oauth2callback during token fetch/save: {e} !!!")
        utils.clear_credentials() # Ensure credentials are cleared on error
        session.pop('post_auth_redirect', None) # Clear redirect target on error
        if utils.should_log(): print("--- OAUTH2CALLBACK END (ERROR) ---")
        return redirect('/') # Redirect to static home page on error

# Logout route remains unchanged for now, seems reasonable.
@auth_bp.route('/logout')
def logout():
    """Clears the session and logs the user out completely."""
    # First, clear credentials
    utils.clear_credentials()
    
    # Clear all OAuth-related session data
    session.pop('oauth_state', None)
    # session.pop('requested_scopes', None) # No longer used
    # session.pop('requested_extended_permissions', None) # No longer used
    # session.pop('current_auth_scopes', None) # No longer used
    session.pop('post_auth_redirect', None)
    
    # Clear any other session data
    session.clear()
    
    # Create a response with cache-control headers to clear browser cache
    # Redirect to static home page '/' which is handled by Vercel
    response = redirect('/') 
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
            // Preserve theme setting
            const currentTheme = localStorage.getItem('theme');
            
            // Clear all localStorage
            localStorage.clear();
            
            // Restore theme setting if it existed
            if (currentTheme) {
                localStorage.setItem('theme', currentTheme);
            }
            
            // Clear all sessionStorage
            sessionStorage.clear();
            
            // Clear cookies related to this site
            function clearSiteCookies() {
                const cookies = document.cookie.split("; ");
                for (let c of cookies) {
                    const [name, ...rest] = c.split("=");
                    // Check if cookie belongs to the current domain or parent domains
                    let domain = window.location.hostname;
                    while (domain) {
                        document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=" + domain + ";";
                        // Move to parent domain
                        const parts = domain.split('.');
                        if (parts.length === 1) break; // Avoid setting cookie on TLD
                        domain = parts.slice(1).join('.');
                    }
                     // Clear for root path without domain specificaiton as well
                    document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                }
            }
            clearSiteCookies();

            
            // Show message
            document.addEventListener('DOMContentLoaded', function() {
                document.getElementById('message').textContent = 'You have been logged out. Redirecting...';
            });
            
            // Redirect to homepage after a short delay
            setTimeout(function() {
                window.location.href = '/'; // Redirect to root
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
    
    # Return the HTML directly, which contains the redirect script
    # Use Flask's make_response to set headers on the HTML content
    from flask import make_response
    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp