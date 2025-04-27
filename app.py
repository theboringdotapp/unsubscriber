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

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for Flask session management

# Google API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify'] # Read, modify (for archiving), send
# Set default REDIRECT_URI (can be overridden in main)
REDIRECT_URI = 'http://127.0.0.1:5001/oauth2callback'
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
    """Process unsubscribe links and archive emails."""
    # Check if this is an HTMX request
    is_htmx_request = request.headers.get('HX-Request') == 'true'
    
    print("\n==== UNSUBSCRIBE REQUEST STARTED ====")
    print(f"Time: {__import__('datetime').datetime.now()}")
    
    service = get_gmail_service()
    if not service:
        print("ERROR: Gmail service not available - authentication required")
        flash("Please login first", "warning")
        return redirect(url_for('index'))
        
    # Get the selected email IDs and unsubscribe links
    try:
        email_ids = request.form.get('final_email_ids', '')
        unsubscribe_links = request.form.get('final_unsubscribe_links', '')
        should_archive = request.form.get('should_archive', 'false').lower() in ('true', 'on', 'yes', '1')
        
        print(f"Received email_ids: {email_ids}")
        print(f"Received unsubscribe_links: {unsubscribe_links}")
        print(f"Should archive: {should_archive}")
        
        # Parse comma-separated values from the form data
        email_ids = email_ids.split(',') if email_ids else []
        # Split by five commas to handle URLs that might contain commas
        unsubscribe_links = unsubscribe_links.split(',,,,,') if unsubscribe_links else []
        
        print(f"Parsed {len(email_ids)} email IDs and {len(unsubscribe_links)} unsubscribe links")
        
        if not email_ids or not unsubscribe_links:
            print("ERROR: No emails selected")
            flash("No emails selected", "warning")
            if is_htmx_request:
                return render_template('partials/unsubscribe_result.html', success=False, message="No emails selected")
            return redirect(url_for('index'))
            
        # Process each unsubscribe link and archive the email
        results = []
        for i, (email_id, link) in enumerate(zip(email_ids, unsubscribe_links)):
            print(f"\nProcessing email {i+1}/{len(email_ids)}:")
            print(f"  ID: {email_id}")
            print(f"  Link: {link}")
            
            try:
                # Visit the unsubscribe link
                if not MOCK_API:
                    print(f"  Sending GET request to: {link}")
                    response = requests.get(link, timeout=5)  # Set a reasonable timeout
                    status = response.status_code
                    print(f"  Response status: {status}")
                else:
                    # Mock a successful request
                    status = 200
                    print(f"  MOCK MODE: Simulating successful GET request (status 200)")
                
                # Archive the email if the should_archive flag is set
                if should_archive:
                    if not MOCK_API:
                        print(f"  Archiving email (removing from INBOX)")
                        service.users().messages().modify(
                            userId='me',
                            id=email_id,
                            body={'removeLabelIds': ['INBOX']}
                        ).execute()
                        print(f"  Email successfully archived")
                    else:
                        print(f"  MOCK MODE: Simulating successful archive")
                else:
                    print(f"  Skipping archive as per user preference")
                
                # Record the result
                success = 200 <= status < 300  # HTTP success status range
                archived = should_archive
                results.append({
                    'email_id': email_id,
                    'status': status,
                    'success': success,
                    'archived': archived
                })
                print(f"  Result: {'SUCCESS' if success else 'FAILED'}")
                
            except Exception as e:
                # Record the failure
                print(f"  ERROR: {str(e)}")
                results.append({
                    'email_id': email_id,
                    'status': 'Error',
                    'error': str(e),
                    'success': False,
                    'archived': False
                })
        
        success_count = sum(1 for result in results if result.get('success', False))
        archive_count = sum(1 for result in results if result.get('archived', False))
        print(f"\nProcessed {len(results)} unsubscribe requests. {success_count} succeeded, {len(results) - success_count} failed.")
        print(f"Archived {archive_count} emails.")
        
        if is_htmx_request:
            print("Returning HTMX response")
            return render_template(
                'partials/unsubscribe_result.html',
                success=True,
                results=results,
                success_count=success_count,
                archive_count=archive_count,
                total_count=len(results),
                should_archive=should_archive
            )
        
        # Flash a message with the results
        message = f"Processed {len(results)} unsubscribe requests. {success_count} succeeded."
        if should_archive:
            message += f" {archive_count} emails were archived."
        status = "success" if success_count == len(results) else "info"
        print(f"Flashing message: {message} (status: {status})")
        flash(message, status)
        
        print("==== UNSUBSCRIBE REQUEST COMPLETED ====\n")
        # Clear the session storage by returning JavaScript
        # This doesn't need to be done for HTMX requests, as we'll handle it in the template
        return redirect(url_for('index'))
        
    except Exception as e:
        error_msg = f"Error processing unsubscribe requests: {e}"
        print(f"ERROR: {error_msg}")
        print("==== UNSUBSCRIBE REQUEST FAILED ====\n")
        flash(error_msg, "error")
        if is_htmx_request:
            return render_template('partials/unsubscribe_result.html', success=False, message=f"Error: {e}")
        return redirect(url_for('index'))


if __name__ == '__main__':
    # Make sure OAUTHLIB_INSECURE_TRANSPORT is set for local testing over HTTP
    # In production, use HTTPS
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(debug=True, port=5000) 