import os
import pickle
import base64
import email
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from flask import Flask, render_template, redirect, url_for, request, session, flash
import requests

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for Flask session management

# Google API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify'] # Read, modify (for archiving), send
REDIRECT_URI = 'http://127.0.0.1:5000/oauth2callback'
CREDENTIALS_FILE = 'credentials.json' # Download from Google Cloud Console

# --- Mocking Setup ---
MOCK_API = True # Set to False to use the real Gmail API

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
    """Creates Google OAuth Flow."""
    print("--- GET_GOOGLE_AUTH_FLOW START ---") # DEBUG
    # TODO: Load client secrets from CREDENTIALS_FILE
    try:
        print(f"Attempting to load credentials from: {CREDENTIALS_FILE}") # DEBUG
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"!!! ERROR: {CREDENTIALS_FILE} not found! !!!") # DEBUG
            # Maybe raise an error here or return None, depends on desired handling
            return None # Indicate failure

        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI)
        print(f"Successfully created Flow object.") # DEBUG
        print("--- GET_GOOGLE_AUTH_FLOW END ---") # DEBUG
        return flow
    except Exception as e:
        print(f"!!! ERROR in get_google_auth_flow loading/parsing {CREDENTIALS_FILE}: {e} !!!") # DEBUG
        # It's crucial to see if an exception happens here
        # Depending on the app structure, might want to raise e or return None
        # Returning None for now to potentially allow Flask to handle it
        return None

def get_gmail_service():
    """Creates and returns a Gmail API service instance."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                flash(f"Error refreshing credentials: {e}. Please re-authenticate.", "error")
                # Force re-authentication if refresh fails
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                return None
        else:
            # Credentials not found or invalid, require login
            return None # Indicate that authentication is needed

        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        flash(f"Error building Gmail service: {e}", "error")
        return None


def find_unsubscribe_links(message_data):
    """Parses email headers and body for unsubscribe links."""
    unsubscribe_info = {"header_link": None, "body_link": None}
    try:
        # Check List-Unsubscribe Header first
        headers = message_data.get('payload', {}).get('headers', [])
        for header in headers:
            if header['name'].lower() == 'list-unsubscribe':
                # Extract URL from header, often enclosed in < >
                value = header['value']
                if '<http' in value:
                    start = value.find('<') + 1
                    end = value.find('>')
                    if start < end:
                         unsubscribe_info["header_link"] = value[start:end]
                         break # Prefer header link if found
                # Sometimes it's just the URL
                elif value.strip().startswith('http'):
                     unsubscribe_info["header_link"] = value.strip()
                     break

        # TODO: If no header link, search body (requires decoding payload)
        # This part is more complex due to various encodings and HTML/text parts
        # Add body parsing logic here if needed for MVP v2

    except Exception as e:
        print(f"Error parsing message for unsubscribe link: {e}") # Log error

    return unsubscribe_info


# --- Flask Routes ---

@app.route('/')
def index():
    """Home page: Check credentials and show scan button or login."""
    service = get_gmail_service()
    authenticated = bool(service) # Check if service object exists
    # Store auth status in session for base template?
    # session['authenticated'] = authenticated # Be careful with session management
    return render_template('index.html', authenticated=authenticated)

@app.route('/login')
def login():
    """Initiates the Google OAuth flow."""
    if os.path.exists('token.pickle'):
         os.remove('token.pickle') # Remove old token if forcing login
    flow = get_google_auth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')
    session['state'] = state # Store state to prevent CSRF
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Handles the OAuth redirect from Google."""
    print("--- OAUTH2CALLBACK START ---") # DEBUG
    print(f"Request URL: {request.url}") # DEBUG
    print(f"Session state: {session.get('state')}") # DEBUG
    print(f"Request args state: {request.args.get('state')}") # DEBUG
    state = session.get('state')
    # CSRF check
    if not state or state != request.args.get('state'):
        print("!!! STATE MISMATCH ERROR !!!") # DEBUG
        flash('State mismatch error. Potential CSRF attack.', 'error')
        return redirect(url_for('index'))

    print("State check passed.") # DEBUG
    flow = get_google_auth_flow()
    try:
        print("Attempting to fetch token...") # DEBUG
        # Use the authorization server's response to fetch the OAuth 2.0 tokens.
        flow.fetch_token(authorization_response=request.url)
        print("Token fetched successfully.") # DEBUG
    except Exception as e:
         print(f"!!! ERROR FETCHING TOKEN: {e} !!!") # DEBUG
         flash(f"Error fetching token: {e}", "error")
         return redirect(url_for('index'))

    credentials = flow.credentials
    # Save the credentials for the next run
    try:
        print("Attempting to save token to pickle file...") # DEBUG
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)
        print("Token saved successfully.") # DEBUG
    except Exception as e:
        print(f"!!! ERROR SAVING TOKEN: {e} !!!") # DEBUG
        flash(f"Error saving token: {e}", "error")
        # Decide if we should redirect or raise here - redirecting for now
        return redirect(url_for('index'))


    print("--- OAUTH2CALLBACK END ---") # DEBUG
    flash('Authentication successful!', 'success')
    return redirect(url_for('index'))


@app.route('/scan', methods=['GET'])
def scan_emails():
    """Fetches emails and looks for unsubscribe links. Uses MOCK_API if enabled."""
    if not MOCK_API:
        service = get_gmail_service()
        if not service:
            flash("Authentication required.", "warning")
            return redirect(url_for('login'))
        authenticated = True
    else:
        # When mocking, assume authenticated for testing scan page directly
        service = None # No real service needed
        authenticated = True # Assume authenticated
        flash("API Mocking Enabled", "info")


    page_token = request.args.get('token')
    unsubscribe_candidates = []
    next_page_token = None

    try:
        if MOCK_API:
            results = _get_mock_message_list(page_token=page_token)
        else:
            results = service.users().messages().list(
                userId='me',
                q='label:inbox',
                maxResults=50, # Adjust page size if needed
                pageToken=page_token
            ).execute()

        messages = results.get('messages', [])
        next_page_token = results.get('nextPageToken') # Get token regardless of mock/real

        if not messages and not page_token: # Only show 'no messages' if it's the first page
            flash("No messages found in your inbox (or mock data is empty).", "info")
            return redirect(url_for('index'))

        processed_ids = set()

        for msg_ref in messages:
            msg_id = msg_ref['id']
            if msg_id in processed_ids:
                continue
            processed_ids.add(msg_id)

            try:
                if MOCK_API:
                    message = _get_mock_message_details(msg_id)
                else:
                    message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

                subject = ""
                sender = ""
                headers = message.get('payload', {}).get('headers', [])
                for header in headers:
                    name_lower = header['name'].lower()
                    if name_lower == 'subject':
                        subject = header['value']
                    elif name_lower == 'from':
                        # Basic sender parsing (might need refinement for complex names)
                        from_val = header['value']
                        if '<' in from_val:
                            try:
                                sender = from_val[:from_val.rindex('<')].strip().replace('"', '')
                                if not sender: # Handle cases like "<email@example.com>"
                                     sender = from_val[from_val.rindex('<')+1:from_val.rindex('>')]
                            except ValueError:
                                sender = from_val # Fallback
                        else:
                            sender = from_val # Assume it's just the email
                        sender = sender or "Unknown Sender" # Ensure sender is not empty

                unsubscribe_info = find_unsubscribe_links(message) # Use the real parsing logic
                link = unsubscribe_info.get("header_link") or unsubscribe_info.get("body_link")

                if link:
                    unsubscribe_candidates.append({
                        'id': msg_id,
                        'subject': subject,
                        'sender': sender,
                        'unsubscribe_link': link
                    })
            except Exception as get_err:
                print(f"Error processing message {msg_id}: {get_err}")
                # Optionally flash a message or just log for mocks/real API
                if not MOCK_API:
                     flash(f"Error fetching details for message {msg_id}.", "warning")
                continue

    except Exception as e:
        # Handle potential errors from list call or general processing
        error_message = f"An error occurred while scanning emails: {e}"
        if not MOCK_API and ('invalid_grant' in str(e).lower() or 'credentials' in str(e).lower()):
             if os.path.exists('token.pickle'):
                 os.remove('token.pickle')
             flash("Authentication error. Please log in again.", "error")
             return redirect(url_for('login'))
        else:
             flash(error_message, "error")
             return redirect(url_for('index'))

    # Pass authenticated status and token to template
    return render_template('scan_results.html',
                           emails=unsubscribe_candidates,
                           next_page_token=next_page_token,
                           authenticated=authenticated)


@app.route('/unsubscribe', methods=['POST'])
def unsubscribe_and_archive():
    """Processes selected emails: calls unsubscribe link and archives."""
    service = get_gmail_service()
    if not service:
        flash("Authentication required.", "warning")
        return redirect(url_for('login'))

    # Get data from the hidden fields populated by JavaScript
    final_ids_str = request.form.get('final_email_ids', '')
    final_links_str = request.form.get('final_unsubscribe_links', '')

    selected_ids = final_ids_str.split(',') if final_ids_str else []
    # Use the custom separator to split links correctly
    unsubscribe_links = final_links_str.split(',,,,,') if final_links_str else []

    # Basic validation: Ensure the number of IDs and links match
    if len(selected_ids) != len(unsubscribe_links):
        flash("Error: Mismatch between selected email IDs and links.", "error")
        # Redirect back to scan results, potentially losing state without more complex handling
        # For simplicity, redirecting home. Consider redirecting back to scan results
        # if you implement passing the page token back or storing it.
        return redirect(url_for('index'))

    if not selected_ids:
        flash("No emails selected for unsubscribing.", "warning")
        # Redirect back? Let's redirect home for now.
        return redirect(url_for('index'))

    processed_count = 0
    error_count = 0
    skipped_mailto_count = 0

    # Pair IDs with their links
    actions = dict(zip(selected_ids, unsubscribe_links))

    for msg_id, link in actions.items():
        if not msg_id or not link: # Skip empty entries if splitting resulted in them
            continue
        try:
            # 1. Attempt to "visit" the unsubscribe link (simple GET request)
            if link.startswith('http'):
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(link, timeout=15, headers=headers) # Increased timeout slightly
                    response.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)
                    print(f"Visited unsubscribe link for {msg_id}: {link} (Status: {response.status_code})")
                    # Archive only if HTTP request was successful
                    service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={'removeLabelIds': ['INBOX']}
                    ).execute()
                    processed_count += 1
                    print(f"Archived email {msg_id} after successful unsubscribe visit.")

                except requests.exceptions.RequestException as req_err:
                    # Log error but *don't* archive if the unsubscribe failed
                    print(f"Warning: Failed to visit unsubscribe link {link} for {msg_id}: {req_err}. Email NOT archived.")
                    error_count += 1 # Count as an error if the unsubscribe failed

            elif link.startswith('mailto:'):
                print(f"Info: Unsubscribe for {msg_id} requires sending an email: {link}. Manual action needed. Email NOT archived.")
                skipped_mailto_count += 1
                # Don't archive mailto links as action wasn't automatically completed
                pass
            else:
                 print(f"Warning: Unknown link type for {msg_id}: {link}. Email NOT archived.")
                 error_count += 1 # Count as error if link type is unknown

            # Removed the separate archiving step here - it's now conditional on HTTP success

        except Exception as e:
            error_count += 1
            print(f"Error processing email {msg_id}: {e}")
            # Don't stop the whole process, just note the error

    flash_message = f"Attempted to process {len(selected_ids)} emails. Successfully unsubscribed and archived: {processed_count}. "
    if skipped_mailto_count > 0:
        flash_message += f"Skipped {skipped_mailto_count} mailto links (manual action required). "
    if error_count > 0:
        flash_message += f"Encountered {error_count} errors (failed to visit link or other issue - check logs)."

    flash(flash_message, "info")
    # Clear selection after processing
    # session.pop(storageKey, None) # This won't work as storage is client-side
    # Client-side needs to clear its own storage upon success indication, maybe via redirect param?
    # For now, rely on user starting fresh or manually clearing session.

    return redirect(url_for('index'))


if __name__ == '__main__':
    # Make sure OAUTHLIB_INSECURE_TRANSPORT is set for local testing over HTTP
    # In production, use HTTPS
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(debug=True, port=5000) 