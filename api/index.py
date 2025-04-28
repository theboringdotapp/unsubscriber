import os
import pickle
import base64
import email
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from flask import Flask, render_template, redirect, url_for, request, session, flash
import requests
import json
import sys
import argparse
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText

# Explicitly tell Flask the template folder is in the root directory
# Calculate the path to the root directory relative to this file (api/index.py)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(project_root, 'templates')

app = Flask(__name__, template_folder=template_dir)

# Set a persistent secret key from an environment variable for session management
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
if not SECRET_KEY:
    # Provide a warning and an insecure default for local testing if the env var isn't set.
    # The environment variable MUST be set for production/preview deployments on Vercel.
    print("WARNING: FLASK_SECRET_KEY environment variable not set. Using insecure default for local dev ONLY.")
    SECRET_KEY = 'dev-secret-key-replace-this-in-production' # Insecure default
app.secret_key = SECRET_KEY
print(f"--- Flask App Initialized. Using Secret Key: {app.secret_key[:5]}...{app.secret_key[-5:] if len(app.secret_key) > 10 else ''} ---") # DEBUG: Confirm key usage

# Google API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify'] # Read, modify (for archiving), send

# --- Vercel Specific Configuration ---
# Prioritize the production URL for OAuth consistency, fall back to deployment URL, then localhost
PROD_URL = os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')
DEPLOY_URL = os.environ.get('VERCEL_URL')
VERCEL_ENV = os.environ.get('VERCEL_ENV', 'development') # Get Vercel environment type

if PROD_URL and VERCEL_ENV == 'production':
    # Use HTTPS for the production domain
    BASE_URL = f"https://{PROD_URL}"
    print(f"--- Using Production URL (HTTPS): {BASE_URL} ---")
elif DEPLOY_URL:
    # Use HTTP for vercel dev (localhost) or preview deployments
    BASE_URL = f"http://{DEPLOY_URL}" 
    print(f"--- Using Deployment URL (HTTP): {BASE_URL} ---")
else:
    # Fallback for truly local execution (e.g. `python api/index.py`)
    BASE_URL = 'http://127.0.0.1:5001' # Default for local development
    print(f"--- Using Localhost Fallback URL (HTTP): {BASE_URL} ---")

REDIRECT_URI = f'{BASE_URL}/oauth2callback'
print(f"--- Final REDIRECT_URI: {REDIRECT_URI} ---") # Debugging
# --- End Vercel Specific Configuration ---


CREDENTIALS_FILE = 'credentials.json' # Download from Google Cloud Console

# --- Mocking Setup ---
MOCK_API = False # Set to False to use the real Gmail API

def _get_mock_message_list(page_token=None):
    """Returns a mock response similar to messages.list()."""
    print("--- USING MOCK MESSAGE LIST ---")
    # Simulate pagination
    all_mock_messages = [
        {'id': 'mock_id_1', 'threadId': 'thread_1'},
        {'id': 'mock_id_2', 'threadId': 'thread_2'},
        {'id': 'mock_id_3_no_link', 'threadId': 'thread_3'},
        {'id': 'mock_id_4_mailto', 'threadId': 'thread_4'},
        {'id': 'mock_id_5', 'threadId': 'thread_5'},
        # Add more to test pagination
        {'id': 'mock_id_6', 'threadId': 'thread_6'},
        {'id': 'mock_id_7', 'threadId': 'thread_7'},
        {'id': 'mock_id_8', 'threadId': 'thread_8'},
        {'id': 'mock_id_9', 'threadId': 'thread_9'},
        {'id': 'mock_id_10', 'threadId': 'thread_10'},
    ]
    page_size = 5 # Simulate smaller pages for testing
    start_index = 0
    if page_token:
        try:
            start_index = int(page_token)
        except ValueError:
            start_index = 0 # Default to first page on bad token

    end_index = start_index + page_size
    messages_page = all_mock_messages[start_index:end_index]

    next_page_token = str(end_index) if end_index < len(all_mock_messages) else None

    return {
        'messages': messages_page,
        'nextPageToken': next_page_token,
        'resultSizeEstimate': len(messages_page)
    }

def _get_mock_message_details(msg_id):
    """Returns mock message details based on ID."""
    print(f"--- USING MOCK MESSAGE DETAILS FOR ID: {msg_id} ---")
    details = {
        'mock_id_1': {
            'id': 'mock_id_1',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Mock Newsletter A'},
                    {'name': 'From', 'value': 'Sender A <sender-a@example.com>'},
                    {'name': 'List-Unsubscribe', 'value': '<http://example.com/unsubscribe/aaa>'}
                ]
            }
        },
        'mock_id_2': {
            'id': 'mock_id_2',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Mock Promotions B'},
                    {'name': 'From', 'value': 'Sender B <sender-b@example.com>'},
                    {'name': 'List-Unsubscribe', 'value': 'http://example.com/unsub/bbb'} # No angle brackets
                ]
                # Could add body/parts here later if needed for body scanning mock
            }
        },
        'mock_id_3_no_link': {
             'id': 'mock_id_3_no_link',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Just a Regular Email'},
                    {'name': 'From', 'value': 'Friend <friend@example.com>'},
                ]
            }
        },
         'mock_id_4_mailto': {
             'id': 'mock_id_4_mailto',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Old Style List (Mailto)'},
                    {'name': 'From', 'value': 'Old List <old@example.com>'},
                     {'name': 'List-Unsubscribe', 'value': '<mailto:unsubscribe@example.com?subject=removeme>'}
                ]
            }
        },
         'mock_id_5': {
             'id': 'mock_id_5',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Another Mock Promotion'},
                    {'name': 'From', 'value': 'Sender A <sender-a@example.com>'}, # Same sender as #1
                    {'name': 'List-Unsubscribe', 'value': '<http://example.com/unsubscribe/aaa_v2>'}
                ]
            }
        },
         # Add details for page 2 mocks
         'mock_id_6': {
             'id': 'mock_id_6',
            'payload': { 'headers': [ {'name': 'Subject', 'value': 'Page 2 - Email 6'}, {'name': 'From', 'value': 'Sender C'}, {'name': 'List-Unsubscribe', 'value': '<http://example.com/unsub/ccc>'}]}
        },
         'mock_id_7': {
             'id': 'mock_id_7',
            'payload': { 'headers': [ {'name': 'Subject', 'value': 'Page 2 - Email 7'}, {'name': 'From', 'value': 'Sender D'}, {'name': 'List-Unsubscribe', 'value': '<http://example.com/unsub/ddd>'}]}
        },
         'mock_id_8': {
             'id': 'mock_id_8',
            'payload': { 'headers': [ {'name': 'Subject', 'value': 'Page 2 - Email 8 No Link'}, {'name': 'From', 'value': 'Sender E'}]}
        },
         'mock_id_9': {
             'id': 'mock_id_9',
            'payload': { 'headers': [ {'name': 'Subject', 'value': 'Page 2 - Email 9'}, {'name': 'From', 'value': 'Sender C'}, {'name': 'List-Unsubscribe', 'value': '<http://example.com/unsub/ccc_v2>'}]} # Same sender C
        },
         'mock_id_10': {
             'id': 'mock_id_10',
            'payload': { 'headers': [ {'name': 'Subject', 'value': 'Page 2 - Email 10'}, {'name': 'From', 'value': 'Sender F'}, {'name': 'List-Unsubscribe', 'value': '<http://example.com/unsub/fff>'}]}
        },
    }
    return details.get(msg_id, {'id': msg_id, 'payload': {'headers': []}}) # Return empty payload if not found

# --- Helper Functions ---

def get_google_auth_flow():
    """Creates Google OAuth Flow.
    Attempts to load credentials from GOOGLE_CREDENTIALS_JSON environment variable first.
    Falls back to loading from CREDENTIALS_FILE if the env var is not set.
    """
    print("--- GET_GOOGLE_AUTH_FLOW START ---") # DEBUG

    credentials_json_content = os.environ.get('GOOGLE_CREDENTIALS_JSON')

    if credentials_json_content:
        print("Loading credentials from GOOGLE_CREDENTIALS_JSON environment variable.") # DEBUG
        try:
            # The environment variable contains the JSON content directly
            client_config = json.loads(credentials_json_content)
            # Ensure it's the expected structure (usually nested under 'web' or 'installed')
            if 'web' not in client_config and 'installed' not in client_config:
                 print("!!! ERROR: GOOGLE_CREDENTIALS_JSON does not contain 'web' or 'installed' key. !!!")
                 return None
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI)
            print("Successfully created Flow object from environment variable.") # DEBUG
            print("--- GET_GOOGLE_AUTH_FLOW END ---") # DEBUG
            return flow
        except json.JSONDecodeError as e:
             print(f"!!! ERROR: Failed to parse JSON from GOOGLE_CREDENTIALS_JSON: {e} !!!") # DEBUG
             return None
        except Exception as e:
            print(f"!!! ERROR creating Flow from environment variable config: {e} !!!") # DEBUG
            return None
    else:
        print("GOOGLE_CREDENTIALS_JSON not found. Falling back to credentials file.") # DEBUG
        # Ensure credentials file is accessible relative to this script's location
        script_dir = os.path.dirname(__file__)
        abs_credentials_file = os.path.join(script_dir, '..', CREDENTIALS_FILE) # Go up one dir from api/
        print(f"Attempting to load credentials from file: {abs_credentials_file}") # DEBUG

        if not os.path.exists(abs_credentials_file):
            print(f"!!! ERROR: {abs_credentials_file} not found! Ensure '{CREDENTIALS_FILE}' is in the project root OR set GOOGLE_CREDENTIALS_JSON env var. !!!") # DEBUG
            return None # Indicate failure

        try:
            flow = Flow.from_client_secrets_file(
                abs_credentials_file,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI)
            print(f"Successfully created Flow object from file.") # DEBUG
            print("--- GET_GOOGLE_AUTH_FLOW END ---") # DEBUG
            return flow
        except Exception as e:
            print(f"!!! ERROR in get_google_auth_flow loading/parsing {abs_credentials_file}: {e} !!!") # DEBUG
            return None

# --- Token Handling Modification for Vercel ---
# Vercel's filesystem is ephemeral for serverless functions.
# Storing tokens in session is a simple way for demo purposes, but has limitations.
# A more robust solution would use a database or secure external storage.

def save_credentials(creds):
    """Saves credentials to the session."""
    try:
        session['credentials'] = pickle.dumps(creds).decode('latin1') # Store pickled creds as string
        print("--- DEBUG: save_credentials: Successfully pickled and stored credentials in session. ---")
    except Exception as e:
        print(f"--- DEBUG: save_credentials: ERROR pickling/storing credentials: {e} ---")

def load_credentials():
    """Loads credentials from the session."""
    print("--- DEBUG: load_credentials: Attempting to load credentials from session. ---")
    creds_pickle = session.get('credentials')
    if creds_pickle:
        print("--- DEBUG: load_credentials: Found 'credentials' key in session. Attempting to unpickle. ---")
        try:
            creds = pickle.loads(creds_pickle.encode('latin1'))
            print("--- DEBUG: load_credentials: Successfully unpickled credentials. ---")
            return creds
        except Exception as e:
            print(f"--- DEBUG: load_credentials: ERROR unpickling credentials: {e} ---")
            # Optionally clear the corrupted session data
            session.pop('credentials', None)
            return None
    else:
        print("--- DEBUG: load_credentials: 'credentials' key NOT found in session. ---")
        return None

def clear_credentials():
     """Clears credentials from the session."""
     session.pop('credentials', None)
     print("Cleared credentials from session.")

# --- End Token Handling Modification ---


def get_gmail_service():
    """Creates and returns a Gmail API service instance using session storage."""
    print("--- DEBUG: get_gmail_service: Attempting to get service. --- ")
    creds = load_credentials()

    if not creds:
        print("--- DEBUG: get_gmail_service: load_credentials returned None. Returning None. --- ")
        return None # Already logged reason inside load_credentials

    print(f"--- DEBUG: get_gmail_service: Credentials loaded. Valid: {creds.valid}, Expired: {creds.expired}, Has Refresh Token: {bool(creds.refresh_token)} ---")

    # If there are no (valid) credentials available, return None to trigger login flow.
    if not creds.valid:
        print("--- DEBUG: get_gmail_service: Credentials are not valid. Checking refresh token... ---")
        if creds.expired and creds.refresh_token:
            print("--- DEBUG: get_gmail_service: Credentials expired and refresh token exists. Attempting refresh... ---")
            try:
                creds.refresh(Request())
                print("--- DEBUG: get_gmail_service: Token refreshed successfully. Saving new credentials. ---")
                save_credentials(creds) # Save the refreshed credentials
            except Exception as e:
                flash(f"Error refreshing credentials: {e}. Please re-authenticate.", "error")
                print(f"--- DEBUG: get_gmail_service: Token refresh FAILED: {e} ---")
                clear_credentials() # Clear bad credentials
                return None # Force re-authentication
        else:
            # Credentials not found, invalid, or no refresh token
            print("--- DEBUG: get_gmail_service: Credentials invalid/expired OR no refresh token. Clearing credentials and returning None. ---")
            clear_credentials() # Ensure clean state
            return None # Indicate that authentication is needed

    # If we reach here, creds should be valid (either loaded or refreshed)
    print("--- DEBUG: get_gmail_service: Credentials appear valid. Building Gmail service... ---")
    try:
        # Disable discovery cache for Vercel's ephemeral filesystem
        service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        print("--- DEBUG: get_gmail_service: Gmail service built successfully. Returning service object. ---")
        return service
    except Exception as e:
        flash(f"Error building Gmail service: {e}", "error")
        print(f"--- DEBUG: get_gmail_service: ERROR building Gmail service: {e}. Returning None. ---")
        return None


def find_unsubscribe_links(message_data):
    """Parses email headers and body for unsubscribe links."""
    unsubscribe_info = {"header_link": None, "body_link": None, "mailto_link": None} # Added mailto
    try:
        # Check List-Unsubscribe Header first
        headers = message_data.get('payload', {}).get('headers', [])
        for header in headers:
            if header['name'].lower() == 'list-unsubscribe':
                # Extract URL from header, often enclosed in < >
                value = header['value']
                links = []
                # Handle multiple links (comma-separated) - RFC 2369
                for part in value.split(','):
                    part = part.strip()
                    link = None
                    if '<mailto:' in part:
                        start = part.find('<') + 1
                        end = part.find('>')
                        if start < end:
                           link = part[start:end]
                           unsubscribe_info["mailto_link"] = link # Store first mailto link found
                           # Don't break, might be http link too
                    elif '<http' in part:
                        start = part.find('<') + 1
                        end = part.find('>')
                        if start < end:
                            link = part[start:end]
                            # Prefer HTTPS link if available
                            if not unsubscribe_info["header_link"] or link.startswith('https'):
                                unsubscribe_info["header_link"] = link
                    elif part.strip().startswith('http'):
                         link = part.strip()
                          # Prefer HTTPS link if available
                         if not unsubscribe_info["header_link"] or link.startswith('https'):
                            unsubscribe_info["header_link"] = link
                    elif part.strip().startswith('mailto:'):
                         link = part.strip()
                         unsubscribe_info["mailto_link"] = link # Store first mailto link found


                # If we found an http link, we prioritize it and stop
                if unsubscribe_info["header_link"]:
                    break
                # If only mailto was found so far, keep looking in case http exists
                # If loop finishes, mailto link (if found) will remain


        # TODO: If no header link, search body (requires decoding payload)
        # This part is more complex due to various encodings and HTML/text parts
        # Add body parsing logic here if needed for MVP v2

    except Exception as e:
        print(f"Error parsing message for unsubscribe link: {e}") # Log error

    # Return the first valid link found (prefer HTTP over mailto)
    if unsubscribe_info["header_link"]:
        return unsubscribe_info["header_link"], "header_http"
    elif unsubscribe_info["mailto_link"]:
         return unsubscribe_info["mailto_link"], "header_mailto"
    else:
        # TODO: Add body link return if implemented
        return None, None


# --- Flask Routes ---

@app.route('/')
def index():
    """Home page: Check credentials and show scan button or login."""
    service = get_gmail_service() # Checks session for credentials
    authenticated = bool(service)
    print(f"Index route: authenticated={authenticated}") # Debugging
    # Make sure templates are found relative to the root, not api/
    return render_template('index.html', authenticated=authenticated)

@app.route('/login')
def login():
    """Initiates the Google OAuth flow."""
    # Always clear old credentials from session before starting flow
    clear_credentials()
    print("Starting login flow, cleared session credentials.")

    flow = get_google_auth_flow()
    if not flow:
         flash("Could not load credentials configuration. Please check server logs.", "error")
         return redirect(url_for('index'))

    # --- Debugging Redirect URI ---
    print(f"[Login Route] Using Flow object: {flow}")
    print(f"[Login Route] Redirect URI from flow object: {flow.redirect_uri}")
    print(f"[Login Route] Redirect URI constructed earlier: {REDIRECT_URI}")
    # --- End Debugging ---

    try:
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Request refresh token
            prompt='consent',       # Force consent screen for refresh token
            include_granted_scopes='true')
        session['oauth_state'] = state # Store state to prevent CSRF
        print(f"Generated authorization URL: {authorization_url}") # Debugging
        print(f"Stored state in session: {state}") # Debugging
        return redirect(authorization_url)
    except Exception as e:
        flash(f"Error generating authorization URL: {e}", "error")
        print(f"Error generating authorization URL: {e}") # Debugging
        return redirect(url_for('index'))


@app.route('/oauth2callback')
def oauth2callback():
    """Handles the OAuth callback from Google."""
    print("--- OAUTH2CALLBACK START ---") # Debugging
    state = session.get('oauth_state')
    print(f"Session state: {state}") # Debugging
    print(f"Request args: {request.args}") # Debugging

    # Check for errors from Google
    error = request.args.get('error')
    if error:
        flash(f"Authentication failed: {error}", "error")
        print(f"OAuth callback error: {error}")
        return redirect(url_for('index'))

    # Verify state to prevent CSRF
    request_state = request.args.get('state')
    if not state or state != request_state:
        flash("State mismatch during authentication. Please try again.", "error")
        print(f"State mismatch: session='{state}', request='{request_state}'")
        return redirect(url_for('login')) # Or index? Redirecting to login seems safer

    flow = get_google_auth_flow()
    if not flow:
         flash("Could not load credentials configuration after callback. Check logs.", "error")
         print("get_google_auth_flow returned None during callback.")
         return redirect(url_for('index'))

    try:
        # Use the full URL from the request for token fetching
        # Important for environments behind proxies or complex routing
        authorization_response = request.url
        # Google might require https, handle potential issues if running locally on http
        if BASE_URL.startswith('http://') and ('127.0.0.1' in BASE_URL or 'localhost' in BASE_URL):
            # Check if running via vercel dev which might handle proxying correctly
            # Vercel dev often sets headers like x-forwarded-proto
            forwarded_proto = request.headers.get('x-forwarded-proto')
            if forwarded_proto == 'https':
                 print("--- DEBUG: oauth2callback: Detected x-forwarded-proto=https, using original request.url ---")
                 # Keep original authorization_response
            else:
                 print("--- DEBUG: oauth2callback: Local HTTP detected. Replacing http:// with https:// for Google check. ---")
                 # This is a workaround, Google might still complain depending on client settings
                 authorization_response = authorization_response.replace('http://', 'https://', 1)

        print(f"--- DEBUG: oauth2callback: Fetching token with authorization_response: {authorization_response} ---") # Debugging
        flow.fetch_token(authorization_response=authorization_response)
        print("--- DEBUG: oauth2callback: Token fetched successfully. ---") # Debugging

        creds = flow.credentials
        save_credentials(creds) # Save credentials to session
        print("--- DEBUG: oauth2callback: Credentials theoretically saved to session. ---") # Debugging
        session.pop('oauth_state', None) # Clean up state

        flash("Authentication successful!", "success")
        print("--- OAUTH2CALLBACK END (SUCCESS) ---") # Debugging
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error fetching token or saving credentials: {e}", "error")
        print(f"!!! ERROR in oauth2callback during token fetch/save: {e} !!!") # Debugging
        # Consider clearing potentially partial credentials?
        clear_credentials()
        print("--- OAUTH2CALLBACK END (ERROR) ---") # Debugging
        return redirect(url_for('login')) # Redirect to login on error


@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    clear_credentials()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))


# Limit number of emails to process per scan request

# Modify route to accept token from query args
@app.route('/scan', methods=['GET'])
def scan_emails():
    """Scans recent emails for unsubscribe links, supporting pagination."""
    print("--- SCAN ROUTE START ---") # DEBUG
    page_token = request.args.get('token', None) # Get token for the current page
    print(f"--- SCAN ROUTE: Received page token: {page_token} ---") # DEBUG

    service = get_gmail_service()
    if not service:
        flash("Authentication required.", "warning")
        print("Scan route: Not authenticated.") # DEBUG
        return redirect(url_for('login'))
    
    authenticated = True 

    found_subscriptions = {} 
    # We don't need processed_count for simple pagination based on API pages
    next_page_token = None # Initialize next page token

    try:
        print("Fetching email page.") # DEBUG
        
        if MOCK_API:
             list_response = _get_mock_message_list(page_token=page_token)
        else:
            list_response = service.users().messages().list(
                userId='me',
                maxResults=20, # Consistent page size
                pageToken=page_token, # Use the incoming token
                q='unsubscribe' 
            ).execute()
        # print(f"List response (page): {list_response}") # DEBUG

        messages = list_response.get('messages', [])
        if not messages:
            print("No messages found on this page.") # DEBUG
        else:
            for message_stub in messages:
                msg_id = message_stub['id']
                # print(f"Processing message ID: {msg_id}") # DEBUG - Commented out for clarity

                if MOCK_API:
                    full_message = _get_mock_message_details(msg_id)
                else:
                    # Fetch only headers to find List-Unsubscribe quickly
                    full_message = service.users().messages().get(
                        userId='me', id=msg_id, format='metadata', # metadata includes headers
                        metadataHeaders=['List-Unsubscribe', 'From', 'Subject']
                    ).execute()

                unsubscribe_link, link_type = find_unsubscribe_links(full_message)

                if unsubscribe_link:
                    # print(f"Found link ({link_type}): {unsubscribe_link}") # DEBUG - Commented out for clarity
                    # Extract sender info
                    headers = full_message.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                    if '<' in sender and '>' in sender:
                        clean_sender = sender[:sender.find('<')].strip().replace('"', '')
                        if not clean_sender: 
                             clean_sender = sender[sender.find('<')+1:sender.find('>')]
                    else:
                        clean_sender = sender 

                    # Store details for each email, grouped by sender
                    email_data = {
                         "link": unsubscribe_link,
                         "type": link_type,
                         "full_sender": sender,
                         "subject": subject,
                         "message_id": msg_id
                    }

                    if clean_sender not in found_subscriptions:
                        found_subscriptions[clean_sender] = [email_data] # Initialize list for new sender
                        # print(f"Added first email for sender: {clean_sender} -> Subject: {subject}") # DEBUG - Commented out
                    else:
                        found_subscriptions[clean_sender].append(email_data) # Append to existing list
                        # print(f"Added another email for sender: {clean_sender} -> Subject: {subject}") # DEBUG - Commented out
        
        # Get the token for the *next* page from the API response
        next_page_token = list_response.get('nextPageToken')
        print(f"--- SCAN ROUTE: Next page token from API: {next_page_token} ---") # DEBUG

        print(f"Scan finished for this page. Found {len(found_subscriptions)} unique senders on this page.") # DEBUG

    except Exception as e:
        flash(f"An error occurred during email scan: {e}", "error")
        print(f"!!! ERROR during scan loop: {e} !!!") # DEBUG
        # Pass tokens even on error to potentially allow navigation
        return render_template('scan_results.html', emails=found_subscriptions, error=str(e), authenticated=authenticated, current_page_token=page_token, next_page_token=next_page_token)

    if not found_subscriptions and not page_token: # Show flash only on empty first page
        flash("No emails with unsubscribe links found in the initial scan.", "info")

    # Pass the emails for this page, auth status, and pagination tokens
    return render_template('scan_results.html', emails=found_subscriptions, authenticated=authenticated, current_page_token=page_token, next_page_token=next_page_token)


# --- Add a new helper function to render the modal content ---
def render_unsubscribe_modal_content(success=True, message="", http_link=None):
    """Renders an HTML snippet for the unsubscribe result modal."""
    if success:
        status_message = message or "Request processed successfully!"
        link_message = ""
        if http_link:
             link_message = f'<p class="text-sm mt-2 text-[var(--text-secondary)]">You may need to <a href="{http_link}" target="_blank" class="text-[var(--accent-color)] hover:underline">visit the unsubscribe link</a> manually.</p>'

        html = f"""
        <div class="text-center p-6 flex flex-col items-center">
            <div class="checkmark-container mb-4">
                <svg class="checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                    <circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none"/>
                    <path class="checkmark-check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
                </svg>
            </div>
            <h3 class="text-xl font-semibold text-gray-700 mb-2">Success!</h3>
            <p class="text-gray-600">{status_message}</p>
            {link_message}
            <button class="mt-6 px-6 py-2 bg-[var(--accent-color)] text-white rounded-md hover:bg-[var(--accent-hover)]" onclick="window.removeProcessedEmails()">Done</button>
        </div>
        """
    else:
        status_message = message or "An error occurred."
        html = f"""
        <div class="bg-white rounded-lg p-6 text-center flex flex-col items-center">
            <div class="error-container mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-red-500" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
            </div>
            <h3 class="text-xl font-semibold text-red-600 mb-2">Error</h3>
            <p class="text-gray-600">{status_message}</p>
            <button class="mt-4 px-4 py-2 bg-[var(--accent-color)] text-white rounded-md hover:bg-[var(--accent-hover)]" onclick="window.closeErrorMessage()">Close</button>
        </div>
        """
    return html

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe_and_archive():
    """Handles the unsubscribe action from the form (visiting link/sending email)."""
    service = get_gmail_service()
    if not service:
        if request.headers.get('HX-Request') == 'true':
            return render_unsubscribe_modal_content(success=False, message="Authentication required. Please refresh and log in again."), 401
        else:
            flash("Authentication required.", "warning")
            return redirect(url_for('login'))

    is_ajax = request.headers.get('HX-Request') == 'true'

    final_ids_str = request.form.get('final_email_ids')
    final_links_str = request.form.get('final_unsubscribe_links')
    should_archive = request.form.get('should_archive') == 'true'

    if not final_ids_str or not final_links_str:
         if is_ajax:
             return render_unsubscribe_modal_content(success=False, message="Missing email IDs or links in request."), 400
         else:
            flash("Missing information for unsubscribe action.", "error")
            return redirect(url_for('scan_emails'))

    # Split the combined strings
    ids = final_ids_str.split(',')
    # Links might need more robust splitting if they contain commas
    links_raw = final_links_str.split(',,,,,') 

    # --- Process the first email for now --- 
    # TODO: Implement looping for multiple emails later
    message_id = ids[0] if ids else None
    
    link_type = None
    link = None
    sender = "Selected Email" 
    if message_id:
         try:
            full_message = service.users().messages().get(userId='me', id=message_id, format='metadata', metadataHeaders=['List-Unsubscribe', 'From']).execute()
            link, link_type = find_unsubscribe_links(full_message)
            headers = full_message.get('payload', {}).get('headers', [])
            sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'), sender)
            if '<' in sender_raw and '>' in sender_raw:
                sender = sender_raw[:sender_raw.find('<')].strip().replace('"', '') or sender_raw
            else:
                sender = sender_raw
         except Exception as fetch_err:
             print(f"Error fetching message {message_id} details in unsubscribe: {fetch_err}")
             if is_ajax:
                 return render_unsubscribe_modal_content(success=False, message=f"Could not retrieve details for message {message_id}."), 500
             else:
                flash(f"Could not retrieve details for message {message_id}.", "error")
                return redirect(url_for('scan_emails'))

    if not link or not link_type or not message_id:
         if is_ajax:
             return render_unsubscribe_modal_content(success=False, message="Missing link, type, or message ID after re-fetching."), 400
         else:
            flash("Missing information for unsubscribe action after re-fetching.", "error")
            return redirect(url_for('scan_emails'))

    print(f"--- UNSUBSCRIBE ACTION (Processing ID: {message_id}) --- PENDING MULTI-ITEM IMPL")
    print(f"Link: {link}, Type: {link_type}, Archive: {should_archive}, Sender: {sender}")

    success = False
    error_message = None
    http_link_for_modal = None

    try:
        if link_type == 'header_http':
            http_link_for_modal = link
            print(f"Processing HTTP link for {sender}. Archiving: {should_archive}")
            if should_archive:
                print(f"Archiving message ID: {message_id}")
                service.users().messages().modify(userId='me', id=message_id, body={'removeLabelIds': ['INBOX']}).execute()
                print(f"Archived message {message_id}")
            else:
                print(f"Skipping archive for {message_id}")
            success = True 

        elif link_type == 'header_mailto':
            print(f"Processing mailto link for {sender}. Archiving: {should_archive}")
            parsed_mailto = urlparse(link)
            to_address = parsed_mailto.path
            params = parse_qs(parsed_mailto.query)
            subject = params.get('subject', ['Unsubscribe'])[0]
            body = params.get('body', ['Please unsubscribe me.'])[0]
            if not to_address: raise ValueError("Mailto link missing recipient address.")

            print(f"Sending unsubscribe email to: {to_address}, Subject: {subject}")
            message = MIMEText(body)
            message['to'] = to_address
            message['subject'] = subject
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message_body = {'raw': raw_message}

            if MOCK_API:
                 print("--- MOCK SEND EMAIL ---")
                 sent_message = {'id': f'mock_sent_{message_id}', 'labelIds': ['SENT']}
            else:
                sent_message = service.users().messages().send(userId='me', body=send_message_body).execute()
            print(f"Sent unsubscribe email. Result: {sent_message}")

            if should_archive:
                print(f"Archiving message ID: {message_id}")
                service.users().messages().modify(userId='me', id=message_id, body={'removeLabelIds': ['INBOX']}).execute()
                print(f"Archived message {message_id}")
            else:
                 print(f"Skipping archive for {message_id}")
            success = True

    except Exception as e:
        error_message = f"Error processing unsubscribe for {sender}: {e}"
        print(f"!!! ERROR during unsubscribe action: {error_message} !!!")
        if not is_ajax:
            flash(error_message, "error")

    if is_ajax:
        if success:
            archive_msg = " Email archived." if should_archive else " Email kept in inbox."
            modal_msg = f"Unsubscribe request sent for {sender}.{archive_msg}"
            if link_type == 'header_http':
                 modal_msg = f"Processed archive request for {sender}.{archive_msg}"
            return render_unsubscribe_modal_content(success=True, message=modal_msg, http_link=http_link_for_modal)
        else:
            return render_unsubscribe_modal_content(success=False, message=error_message or "An unknown error occurred.")
    else:
        if success:
             if link_type == 'header_http':
                 session['unsubscribe_success'] = f"Redirecting to unsubscribe page for {sender}... Email { 'archived' if should_archive else 'kept'}."
                 return redirect(link) 
             else:
                 flash(f"Unsubscribe email sent successfully for {sender}! Original email { 'archived' if should_archive else 'kept'}.", "success")
        return redirect(url_for('index'))


# --- Main Execution (for local development) ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gmail Unsubscriber Flask App')
    parser.add_argument('--port', type=int, default=5001, help='Port number to run the Flask app on.')
    parser.add_argument('--debug', action='store_true', help='Run Flask in debug mode.')
    parser.add_argument('--mock', action='store_true', help='Use mock Gmail API data.')
    parser.add_argument('--credentials', type=str, default='credentials.json', help='Path to Google API credentials file.')
    parser.add_argument('--redirect-host', type=str, default='127.0.0.1', help='Hostname for the OAuth redirect URI.')

    args = parser.parse_args()

    # Override globals based on args
    MOCK_API = args.mock
    CREDENTIALS_FILE = args.credentials
    # Construct REDIRECT_URI for local dev based on args
    REDIRECT_URI = f'http://{args.redirect_host}:{args.port}/oauth2callback'
    # Update BASE_URL too if needed, though less critical for local if REDIRECT_URI is explicit
    BASE_URL = f'http://{args.redirect_host}:{args.port}'
    # Update app config/globals before running
    app.config['SERVER_NAME'] = f"{args.redirect_host}:{args.port}" # Needed for url_for outside request context? Maybe not.

    print("--- Application Start (Local Development) ---")
    print(f"Mode: {'Mock API' if MOCK_API else 'Real API'}")
    print(f"Credentials File: {CREDENTIALS_FILE}")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Debug Mode: {args.debug}")
    print(f"Running on: http://{args.redirect_host}:{args.port}")
    print("---------------------------------------------")

    # Note: For Vercel deployment, the `if __name__ == '__main__':` block
    # will not be executed. Vercel uses a WSGI server to run the `app` object directly.
    app.run(host='0.0.0.0', port=args.port, debug=args.debug) 