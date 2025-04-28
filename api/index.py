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

# Explicitly tell Flask the template folder is in the root directory
# Calculate the path to the root directory relative to this file (api/index.py)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(project_root, 'templates')

app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24)  # Needed for Flask session management

# Google API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify'] # Read, modify (for archiving), send

# --- Vercel Specific Configuration ---
# Use VERCEL_URL if available (for deployed environment), otherwise default to localhost for development
BASE_URL = os.environ.get('VERCEL_URL', 'http://127.0.0.1:5001')
# Ensure BASE_URL starts with https:// if it's a Vercel URL, required by Google OAuth usually
if 'vercel.app' in BASE_URL and not BASE_URL.startswith('https://'):
    BASE_URL = f"https://{BASE_URL}"
REDIRECT_URI = f'{BASE_URL}/oauth2callback'
print(f"--- Using REDIRECT_URI: {REDIRECT_URI} ---") # Debugging
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
    session['credentials'] = pickle.dumps(creds).decode('latin1') # Store pickled creds as string

def load_credentials():
    """Loads credentials from the session."""
    if 'credentials' in session:
        try:
            return pickle.loads(session['credentials'].encode('latin1'))
        except Exception as e:
            print(f"Error loading credentials from session: {e}")
            return None
    return None

def clear_credentials():
     """Clears credentials from the session."""
     session.pop('credentials', None)
     print("Cleared credentials from session.")

# --- End Token Handling Modification ---


def get_gmail_service():
    """Creates and returns a Gmail API service instance using session storage."""
    creds = load_credentials()

    # If there are no (valid) credentials available, return None to trigger login flow.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Attempting to refresh token...")
                creds.refresh(Request())
                save_credentials(creds) # Save the refreshed credentials
                print("Token refreshed successfully.")
            except Exception as e:
                flash(f"Error refreshing credentials: {e}. Please re-authenticate.", "error")
                print(f"Token refresh failed: {e}")
                clear_credentials() # Clear bad credentials
                return None # Force re-authentication
        else:
            # Credentials not found, invalid, or no refresh token
            if creds:
                print("Credentials found but invalid/expired and no refresh token.")
            else:
                print("No credentials found in session.")
            clear_credentials() # Ensure clean state
            return None # Indicate that authentication is needed

    # If we reach here, creds should be valid (either loaded or refreshed)
    try:
        service = build('gmail', 'v1', credentials=creds)
        print("Gmail service built successfully.")
        return service
    except Exception as e:
        flash(f"Error building Gmail service: {e}", "error")
        print(f"Error building Gmail service: {e}")
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
        if BASE_URL.startswith('http://') and '127.0.0.1' in BASE_URL:
            print("WARNING: Local development detected (http). Replacing with https for Google's check.")
            # This is a workaround, Google might still complain depending on client settings
            authorization_response = authorization_response.replace('http://', 'https://', 1)

        print(f"Fetching token with authorization_response: {authorization_response}") # Debugging
        flow.fetch_token(authorization_response=authorization_response)
        print("Token fetched successfully.") # Debugging

        creds = flow.credentials
        save_credentials(creds) # Save credentials to session
        print("Credentials saved to session.") # Debugging
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


MAX_SCAN_EMAILS = 50 # Limit number of emails to process per scan request

@app.route('/scan', methods=['GET'])
def scan_emails():
    """Scans recent emails for unsubscribe links."""
    print("--- SCAN ROUTE START ---") # DEBUG
    service = get_gmail_service()
    if not service:
        flash("Authentication required.", "warning")
        print("Scan route: Not authenticated.") # DEBUG
        return redirect(url_for('login'))

    found_subscriptions = {} # Store {sender: link}
    processed_count = 0
    next_page_token = None

    try:
        print("Starting email fetch loop.") # DEBUG
        while processed_count < MAX_SCAN_EMAILS:
            if MOCK_API:
                list_response = _get_mock_message_list(page_token=next_page_token)
            else:
                 # Fetch only messages that are likely bulk/promotions (adjust query as needed)
                 # Consider adding `labelIds: ['CATEGORY_PROMOTIONS']` or similar
                 # Query for common unsubscribe phrases might be too broad
                list_response = service.users().messages().list(
                    userId='me',
                    maxResults=min(20, MAX_SCAN_EMAILS - processed_count), # Fetch smaller batches
                    pageToken=next_page_token,
                    q='unsubscribe' # Simple query, might need refinement
                    # q='label:^ubme OR label:^nu OR category:promotions OR category:social OR category:updates' # More complex example
                ).execute()
            print(f"List response (page): {list_response}") # DEBUG

            messages = list_response.get('messages', [])
            if not messages:
                print("No more messages found matching query.") # DEBUG
                break # Exit loop if no messages

            for message_stub in messages:
                if processed_count >= MAX_SCAN_EMAILS:
                    break # Stop if we hit the overall limit

                msg_id = message_stub['id']
                print(f"Processing message ID: {msg_id}") # DEBUG

                if MOCK_API:
                    full_message = _get_mock_message_details(msg_id)
                else:
                    # Fetch only headers to find List-Unsubscribe quickly
                    full_message = service.users().messages().get(
                        userId='me', id=msg_id, format='metadata', # metadata includes headers
                        metadataHeaders=['List-Unsubscribe', 'From', 'Subject']
                    ).execute()
                # print(f"Full message details (metadata): {full_message}") # DEBUG - Can be verbose

                unsubscribe_link, link_type = find_unsubscribe_links(full_message)

                if unsubscribe_link:
                    print(f"Found link ({link_type}): {unsubscribe_link}") # DEBUG
                    # Extract sender info
                    headers = full_message.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')

                    # Try to get a cleaner sender name (e.g., "Sender Name" from "Sender Name <email@addr>")
                    if '<' in sender and '>' in sender:
                        clean_sender = sender[:sender.find('<')].strip().replace('"', '')
                        if not clean_sender: # If only email was in <>
                             clean_sender = sender[sender.find('<')+1:sender.find('>')]
                    else:
                        clean_sender = sender # Use as is if no brackets

                    # Add to dict, keyed by clean sender, storing details
                    if clean_sender not in found_subscriptions:
                         found_subscriptions[clean_sender] = {
                             "link": unsubscribe_link,
                             "type": link_type, # 'header_http' or 'header_mailto'
                             "full_sender": sender,
                             "subject": subject,
                             "message_id": msg_id # Store one example message ID
                         }
                         print(f"Added subscription: {clean_sender} -> {unsubscribe_link}") # DEBUG
                    else:
                         print(f"Skipping duplicate sender: {clean_sender}") # DEBUG


                processed_count += 1

            next_page_token = list_response.get('nextPageToken')
            if not next_page_token:
                print("No next page token received.") # DEBUG
                break # Exit loop if no more pages

        print(f"Scan finished. Processed {processed_count} emails. Found {len(found_subscriptions)} unique senders.") # DEBUG

    except Exception as e:
        flash(f"An error occurred during email scan: {e}", "error")
        print(f"!!! ERROR during scan loop: {e} !!!") # DEBUG
        # Render template even on error, showing potentially partial results
        return render_template('scan_results.html', subscriptions=found_subscriptions, error=str(e))


    if not found_subscriptions:
        flash("No emails with unsubscribe links found in the recent scan.", "info")

    # Pass the found subscriptions to the template
    return render_template('scan_results.html', subscriptions=found_subscriptions)


@app.route('/unsubscribe', methods=['POST'])
def unsubscribe_and_archive():
    """Handles the unsubscribe action from the form (visiting link/sending email)."""
    service = get_gmail_service()
    if not service:
        flash("Authentication required.", "warning")
        return redirect(url_for('login'))

    link = request.form.get('link')
    link_type = request.form.get('type')
    message_id = request.form.get('message_id')
    sender = request.form.get('sender') # Get sender for flashing message

    print(f"--- UNSUBSCRIBE ACTION ---")
    print(f"Link: {link}, Type: {link_type}, Msg ID: {message_id}, Sender: {sender}")

    if not link or not link_type or not message_id:
        flash("Missing information for unsubscribe action.", "error")
        return redirect(url_for('scan_emails')) # Redirect back to scan? Or maybe index?

    success = False
    error_message = None

    try:
        if link_type == 'header_http':
            # For HTTP links, we redirect the user's browser to the link.
            # We cannot programmatically visit it reliably/securely server-side.
            # We will archive the email *after* redirecting.
            print(f"Redirecting user to HTTP unsubscribe link: {link}")
            # Archive the specific message ID
            try:
                print(f"Archiving message ID: {message_id} after initiating unsubscribe")
                service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body={'removeLabelIds': ['INBOX']} # Archiving = removing INBOX label
                ).execute()
                print(f"Archived message {message_id}")
                # Flash message might be lost on redirect, maybe add param?
                # Or use session to store success message for next page load
                session['unsubscribe_success'] = f"Redirecting to unsubscribe page for {sender}... Email archived."

            except Exception as archive_err:
                 print(f"Error archiving message {message_id}: {archive_err}")
                 # Don't stop the redirect, but maybe log this
                 session['unsubscribe_error'] = f"Redirecting to unsubscribe page for {sender}. Could not archive email: {archive_err}"


            return redirect(link) # Perform the redirect

        elif link_type == 'header_mailto':
            # Handle mailto links - requires parsing and sending an email
            # Example: mailto:unsubscribe@example.com?subject=removeme&body=extra_info
            print(f"Processing mailto link: {link}")
            from urllib.parse import urlparse, parse_qs

            parsed_mailto = urlparse(link)
            to_address = parsed_mailto.path
            params = parse_qs(parsed_mailto.query)
            subject = params.get('subject', ['Unsubscribe'])[0] # Default subject
            body = params.get('body', ['Please unsubscribe me.'])[0] # Default body

            if not to_address:
                 raise ValueError("Mailto link missing recipient address.")

            print(f"Sending unsubscribe email to: {to_address}, Subject: {subject}")

            # Create the email message
            from email.mime.text import MIMEText
            message = MIMEText(body)
            message['to'] = to_address
            message['subject'] = subject
            # Get user's email address to set 'from' - requires profile scope (or use 'me')
            # profile = service.users().getProfile(userId='me').execute()
            # message['from'] = profile['emailAddress']
            # For simplicity, let Gmail API handle 'from' when sending as 'me'

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message_body = {'raw': raw_message}

            # Send the email
            if MOCK_API:
                print("--- MOCK SEND EMAIL ---")
                print(f"To: {to_address}, Subject: {subject}, Body: {body}")
                sent_message = {'id': f'mock_sent_{message_id}', 'labelIds': ['SENT']}
            else:
                sent_message = service.users().messages().send(
                    userId='me',
                    body=send_message_body
                ).execute()
            print(f"Sent unsubscribe email. Result: {sent_message}")

            # Archive the original message
            print(f"Archiving message ID: {message_id}")
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            print(f"Archived message {message_id}")
            success = True


    except Exception as e:
        error_message = f"Error processing unsubscribe for {sender}: {e}"
        print(f"!!! ERROR during unsubscribe action: {error_message} !!!")
        flash(error_message, "error")

    if success:
        flash(f"Unsubscribe email sent successfully for {sender}! Original email archived.", "success")
    # No redirect here for mailto, stay on results page (or maybe back to index?)
    # Need to re-run scan to refresh the list shown
    # TODO: Improve UX - maybe remove the item client-side? Or just rely on flash message?
    # Re-rendering scan results might be confusing if it takes time
    # Redirecting to index might be simplest
    return redirect(url_for('index')) # Redirect to index after mailto action


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