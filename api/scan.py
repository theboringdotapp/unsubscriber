import os
import base64
import email
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText
from flask import Blueprint, redirect, url_for, request, session, flash, render_template, jsonify
from googleapiclient.discovery import build # Needed?
from datetime import datetime # Add datetime import

# Import utils and constants
from . import utils
from . import config # Import config directly

scan_bp = Blueprint('scan', __name__)

# --- Mocking Setup (Keep here or move to utils/config?) ---
MOCK_API = config.MOCK_API # Get from config

def _get_mock_message_list(page_token=None):
    """Returns a mock response similar to messages.list()."""
    print("--- USING MOCK MESSAGE LIST ---")
    # ... (mock implementation as before) ...
    all_mock_messages = [
        {'id': 'mock_id_1', 'threadId': 'thread_1'},
        {'id': 'mock_id_2', 'threadId': 'thread_2'},
        # ... other mocks ...
        {'id': 'mock_id_10', 'threadId': 'thread_10'},
    ]
    page_size = 5 
    start_index = 0
    if page_token:
        try: start_index = int(page_token)
        except ValueError: start_index = 0
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
    # ... (mock details implementation as before) ...
    details = {
        'mock_id_1': {
            'id': 'mock_id_1',
            'payload': {'headers': [{'name': 'Subject', 'value': 'Mock Newsletter A'},{'name': 'From', 'value': 'Sender A <sender-a@example.com>'},{'name': 'List-Unsubscribe', 'value': '<http://example.com/unsubscribe/aaa>'}]}
        },
        # ... other mock details ...
         'mock_id_10': {
             'id': 'mock_id_10',
            'payload': { 'headers': [ {'name': 'Subject', 'value': 'Page 2 - Email 10'}, {'name': 'From', 'value': 'Sender F'}, {'name': 'List-Unsubscribe', 'value': '<http://example.com/unsub/fff>'}]}
        },
    }
    return details.get(msg_id, {'id': msg_id, 'payload': {'headers': []}})

# --- Helper Functions --- 

def find_unsubscribe_links(message_data):
    """Parses email headers for unsubscribe links."""
    # ... (implementation as before) ...
    unsubscribe_info = {"header_link": None, "mailto_link": None}
    try:
        headers = message_data.get('payload', {}).get('headers', [])
        for header in headers:
            if header['name'].lower() == 'list-unsubscribe':
                value = header['value']
                for part in value.split(','):
                    part = part.strip()
                    link = None
                    if '<mailto:' in part:
                        start = part.find('<') + 1
                        end = part.find('>')
                        if start < end:
                           link = part[start:end]
                           unsubscribe_info["mailto_link"] = link
                    elif '<http' in part:
                        start = part.find('<') + 1
                        end = part.find('>')
                        if start < end:
                            link = part[start:end]
                            if not unsubscribe_info["header_link"] or link.startswith('https'):
                                unsubscribe_info["header_link"] = link
                    elif part.strip().startswith('http'):
                         link = part.strip()
                         if not unsubscribe_info["header_link"] or link.startswith('https'):
                            unsubscribe_info["header_link"] = link
                    elif part.strip().startswith('mailto:'):
                         link = part.strip()
                         unsubscribe_info["mailto_link"] = link
                if unsubscribe_info["header_link"]: break
    except Exception as e:
        print(f"Error parsing message for unsubscribe link: {e}")

    if unsubscribe_info["header_link"]: return unsubscribe_info["header_link"], "header_http"
    elif unsubscribe_info["mailto_link"]: return unsubscribe_info["mailto_link"], "header_mailto"
    else: return None, None

def render_unsubscribe_modal_content(success=True, message="", http_link=None):
    """Renders an HTML snippet for the unsubscribe result modal."""
    # ... (implementation as before) ...
    if success:
        status_message = message or "Request processed successfully!"
        link_message = ""
        if http_link: link_message = f'<p class="...">...<a href="{http_link}"...>visit the unsubscribe link</a>...</p>'
        html = f"""<div class="text-center...">...<svg>...</svg><h3>Success!</h3><p>{status_message}</p>{link_message}<button onclick="window.removeProcessedEmails()">Done</button></div>"""
    else:
        status_message = message or "An error occurred."
        html = f"""<div class="bg-white...">...<svg>...</svg><h3>Error</h3><p>{status_message}</p><button onclick="window.closeErrorMessage()">Close</button></div>"""
    # Make sure the full HTML from previous step is here
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

def format_email_date(internal_date_ms):
    """Converts Gmail internal date (milliseconds since epoch) to a readable string."""
    try:
        # Convert milliseconds to seconds
        timestamp_sec = int(internal_date_ms) / 1000
        dt_object = datetime.fromtimestamp(timestamp_sec)
        # Format as something like "Apr 28" or "2023 Dec 25"
        now = datetime.now()
        if dt_object.year == now.year:
            return dt_object.strftime("%b %d") # e.g., Apr 28
        else:
            return dt_object.strftime("%Y %b %d") # e.g., 2023 Dec 25
    except Exception as e:
        print(f"Error formatting date {internal_date_ms}: {e}")
        return "Unknown Date"

# --- Routes --- 

@scan_bp.route('/scan', methods=['GET'])
def scan_emails():
    """Scans recent emails for unsubscribe links, supporting pagination."""
    print("--- SCAN ROUTE START ---")
    page_token = request.args.get('token', None)
    print(f"--- SCAN ROUTE: Received page token: {page_token} ---")

    service = utils.get_gmail_service()
    if not service:
        flash("Authentication required.", "warning")
        print("Scan route: Not authenticated.")
        return redirect(url_for('auth.login')) # Redirect to auth blueprint login
    
    authenticated = True 
    found_subscriptions = {} 
    next_page_token = None 
    
    # Define colors here in Python
    colors = [
        '217 91% 60%', # Blue
        '158 78% 42%', # Green
        '350 89% 60%', # Pink
        '39 95% 55%',  # Orange
        '262 78% 60%', # Purple
        '197 88% 55%', # Cyan
        '22 90% 58%'   # Reddish-Orange
    ]

    try:
        print("Fetching email page.")
        max_scan_emails = config.MAX_SCAN_EMAILS # Get constant from config

        if MOCK_API:
             list_response = _get_mock_message_list(page_token=page_token)
        else:
            list_response = service.users().messages().list(
                userId='me', 
                maxResults=20, 
                pageToken=page_token, 
                q='unsubscribe',
                labelIds=['INBOX']
            ).execute()

        messages = list_response.get('messages', [])
        if not messages: print("No messages found on this page.")
        else:
            for message_stub in messages:
                msg_id = message_stub['id']
                try: # Add try/except around individual message processing
                    if MOCK_API:
                        full_message = _get_mock_message_details(msg_id)
                        # Add mock date if needed for testing
                        full_message['internalDate'] = str(int(datetime.now().timestamp() * 1000))
                    else:
                        full_message = service.users().messages().get(
                            userId='me', id=msg_id, format='metadata',
                            # Request InternalDate along with other headers
                            metadataHeaders=['List-Unsubscribe', 'From', 'Subject'] 
                        ).execute()
                    
                    unsubscribe_link, link_type = find_unsubscribe_links(full_message)
                    
                    if unsubscribe_link:
                        headers = full_message.get('payload', {}).get('headers', [])
                        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                        
                        # Extract and format date
                        internal_date = full_message.get('internalDate', '0')
                        email_date_formatted = format_email_date(internal_date)
                        
                        # Determine clean sender name (used as the primary key)
                        if '<' in sender and '>' in sender:
                            clean_sender = sender[:sender.find('<')].strip().replace('"', '')
                            # If name part is empty, use the email part as fallback
                            if not clean_sender:
                                start = sender.find('<') + 1
                                end = sender.find('>')
                                if start < end:
                                     clean_sender = sender[start:end]
                                else:
                                     clean_sender = sender # Fallback to raw if parsing fails badly
                        else: 
                            clean_sender = sender
                        
                        # Structure the email data
                        email_data = {
                            "id": msg_id,
                            "subject": subject,
                            "date": email_date_formatted,
                            # We might not need link/type/full_sender per email anymore if handling unsubscribe per sender
                            # Keep them for now if needed elsewhere, but check later
                            "link": unsubscribe_link, 
                            "type": link_type, 
                            "full_sender": sender
                        }
                        
                        # Add to the dictionary using the new structure
                        if clean_sender not in found_subscriptions:
                            found_subscriptions[clean_sender] = {
                                'emails': [email_data],
                                # Store the first found unsubscribe link as the primary for the sender group
                                'unsubscribe_link': unsubscribe_link 
                            }
                        else:
                            found_subscriptions[clean_sender]['emails'].append(email_data)
                            # Optionally update the primary link if a new one is found (e.g., prefer https)
                            # For simplicity, we keep the first one found for this sender.
                except Exception as msg_error:
                     print(f"!!! ERROR processing message {msg_id}: {msg_error} !!!")
                     # Optionally skip this email or handle error appropriately

        next_page_token = list_response.get('nextPageToken')
        print(f"--- SCAN ROUTE: Next page token from API: {next_page_token} ---")
        print(f"Scan finished for this page. Found {len(found_subscriptions)} unique senders on this page.")

    except Exception as e:
        flash(f"An error occurred during email scan: {e}", "error")
        print(f"!!! ERROR during scan loop: {e} !!!")
        # Pass colors here too
        return render_template('scan_results.html', subscriptions=found_subscriptions, error=str(e), authenticated=authenticated, current_page_token=page_token, next_page_token=next_page_token, colors=colors)

    if not found_subscriptions and not page_token:
        flash("No emails with unsubscribe links found in the initial scan.", "info")

    # Pass colors to the template context
    return render_template('scan_results.html', subscriptions=found_subscriptions, authenticated=authenticated, current_page_token=page_token, next_page_token=next_page_token, colors=colors)

@scan_bp.route('/unsubscribe', methods=['POST'])
def unsubscribe_and_archive():
    """Handles the unsubscribe action from the form (visiting link/sending email). Now returns JSON."""
    service = utils.get_gmail_service()
    if not service:
        return jsonify({"success": False, "error": "Authentication required. Please refresh and log in again."}), 401

    # Get data from form POST
    email_ids = request.form.getlist('email_ids')
    should_archive = request.form.get('archive') == 'true'
    
    if not email_ids:
        return jsonify({"success": False, "error": "Missing email IDs."}), 400
        
    print(f"--- UNSUBSCRIBE ACTION for IDs: {email_ids}, Archive: {should_archive} ---")
    
    # We only need to process ONE unsubscribe action per SENDER.
    # Fetch details for the first email ID of each sender represented in the list.
    processed_senders = set()
    unsubscribe_actions = [] # List of tuples: (email_id, link_type, link, sender)
    emails_to_archive = set(email_ids) if should_archive else set()
    
    # Batch fetch minimal details for all selected emails to group by sender efficiently
    sender_map = {}
    for msg_id in email_ids:
        try:
            # Fetch only From header initially
            full_message = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From']).execute()
            headers = full_message.get('payload', {}).get('headers', [])
            sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'), None)
            if sender_raw:
                 # Extract email address for more reliable grouping
                sender_email = None
                if '<' in sender_raw and '>' in sender_raw:
                    start = sender_raw.find('<') + 1
                    end = sender_raw.find('>')
                    if start < end: sender_email = sender_raw[start:end]
                
                # Fallback if email isn't in <>
                if not sender_email:
                    # Basic check if it looks like an email address
                    if '@' in sender_raw:
                         sender_email = sender_raw.strip()
                
                # Use raw sender if email extraction fails
                grouping_key = sender_email if sender_email else sender_raw
                
                if grouping_key not in sender_map:
                    sender_map[grouping_key] = {"name": sender_raw, "first_email_id": msg_id}
        except Exception as e:
            print(f"Warning: Failed to fetch initial details for {msg_id}: {e}")
            # Can't group this one, might cause issues later if it was the only one for a sender

    # Now, for each unique sender, fetch full details for the *first* email to get the link
    for sender_key, sender_data in sender_map.items():
        if sender_key in processed_senders:
            continue
        
        first_email_id = sender_data["first_email_id"]
        sender_name = sender_data["name"]
        try:
            full_message = service.users().messages().get(userId='me', id=first_email_id, format='metadata', metadataHeaders=['List-Unsubscribe', 'From']).execute()
            link, link_type = find_unsubscribe_links(full_message)
            if link and link_type:
                # Clean up sender name for display
                if '<' in sender_name and '>' in sender_name:
                    display_sender = sender_name[:sender_name.find('<')].strip().replace('"', '') or sender_name
                else: display_sender = sender_name
                unsubscribe_actions.append((first_email_id, link_type, link, display_sender))
                processed_senders.add(sender_key)
            else:
                print(f"No unsubscribe link found for sender {sender_key} (using email {first_email_id})")
        except Exception as fetch_err:
            print(f"Error fetching full details for {first_email_id} (Sender: {sender_key}): {fetch_err}")

    # --- Perform Unsubscribe Actions ---
    success_count = 0
    fail_count = 0
    errors = []
    http_link_for_modal = None # Store the last HTTP link for potential manual visit

    for msg_id, link_type, link, sender in unsubscribe_actions:
        try:
            print(f"Processing unsubscribe for {sender} via {link_type}")
            if link_type == 'header_http':
                # We don't actually visit the link client-side did this
                # Store it in case user needs it
                http_link_for_modal = link 
                print(f"  - (HTTP link for {sender}: {link})")
                # Mark as success (assuming client-side fetch worked)
                success_count += 1
            elif link_type == 'header_mailto':
                # Parse and send mailto
                parsed_mailto = urlparse(link)
                to_address = parsed_mailto.path
                params = parse_qs(parsed_mailto.query)
                subject = params.get('subject', ['Unsubscribe'])[0]
                body = params.get('body', ['Please unsubscribe me.'])[0]
                
                if not to_address: raise ValueError("Mailto link missing recipient.")
                
                message = MIMEText(body)
                message['to'] = to_address
                message['subject'] = subject
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                send_message_body = {'raw': raw_message}
                
                if MOCK_API:
                    print(f"  - MOCK SEND EMAIL to {to_address} for {sender}")
                else:
                    service.users().messages().send(userId='me', body=send_message_body).execute()
                    print(f"  - Sent mailto for {sender}")
                success_count += 1
        except Exception as e:
            fail_count += 1
            error_detail = f"Failed to process unsubscribe for {sender}: {e}"
            print(f"!!! ERROR: {error_detail} !!!")
            errors.append(error_detail)

    # --- Archive Emails (if requested) ---
    archive_success_count = 0
    archive_fail_count = 0
    archive_errors = []
    if should_archive and emails_to_archive:
        print(f"Archiving {len(emails_to_archive)} emails...")
        for msg_id in emails_to_archive:
            try:
                service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['INBOX']}).execute()
                archive_success_count += 1
            except Exception as e:
                archive_fail_count += 1
                error_detail = f"Failed to archive {msg_id}: {e}"
                print(f"!!! ERROR: {error_detail} !!!")
                archive_errors.append(error_detail)
        print(f"Archiving finished. Success: {archive_success_count}, Fail: {archive_fail_count}")

    # --- Construct Response --- 
    overall_success = fail_count == 0 and archive_fail_count == 0
    message_parts = []
    if success_count > 0:
        message_parts.append(f"Processed {success_count} unsubscribe action{ 's' if success_count != 1 else '' }.")
    if fail_count > 0:
         message_parts.append(f"{fail_count} unsubscribe action{ 's' if fail_count != 1 else '' } failed.")
    if should_archive:
         if archive_success_count > 0:
             message_parts.append(f"Archived {archive_success_count} email{ 's' if archive_success_count != 1 else '' }.")
         if archive_fail_count > 0:
            message_parts.append(f"{archive_fail_count} email{ 's' if archive_fail_count != 1 else '' } failed to archive.")
    elif not should_archive and emails_to_archive: # Explicitly state if archive was off
         message_parts.append("Archiving was disabled.")

    final_message = " ".join(message_parts) if message_parts else "No actions performed."

    response_data = {
        "success": overall_success,
        "message": final_message,
        "details": {
            "unsubscribe_errors": errors,
            "archive_errors": archive_errors
        },
        # Provide the last HTTP link in case manual action is needed
        "http_link": http_link_for_modal if fail_count > 0 else None 
    }

    status_code = 200 if overall_success else 500 # Use 500 if any part failed
    return jsonify(response_data), status_code

# --- New Route for Archiving --- 
@scan_bp.route('/archive', methods=['POST'])
def archive_emails():
    """Archives a list of emails provided by message IDs. Returns JSON."""
    print("--- ARCHIVE ROUTE START ---")
    service = utils.get_gmail_service()
    if not service:
         # Return JSON error for AJAX
        return jsonify({"success": False, "error": "Authentication required."}), 401

    # Expect form data now, not JSON
    message_ids = request.form.getlist('email_ids') 
    if not message_ids:
        print("Archive route: Missing email_ids in form data")
        return jsonify({"success": False, "error": "Missing email IDs"}), 400

    # Check if message_ids is actually a list (it should be from getlist)
    if not isinstance(message_ids, list):
        print("Archive route: email_ids is not a list (unexpected)")
        message_ids = [message_ids] # Attempt to recover if it's a single string
        
    print(f"Archive route: Received {len(message_ids)} IDs to archive.")

    success_count = 0
    fail_count = 0
    errors = []

    for msg_id in message_ids:
        try:
            # print(f"Attempting to archive {msg_id}")
            if MOCK_API:
                print(f"--- MOCK ARCHIVE EMAIL ID: {msg_id} ---")
            else:
                service.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={'removeLabelIds': ['INBOX']} 
                ).execute()
            success_count += 1
        except Exception as e:
            fail_count += 1
            error_detail = f"Failed to archive {msg_id}: {e}"
            print(f"!!! ERROR: {error_detail} !!!")
            errors.append(error_detail)

    print(f"Archive route: Finished. Success: {success_count}, Failed: {fail_count}")
    overall_success = fail_count == 0
    final_message = f"Successfully archived {success_count} email{ 's' if success_count != 1 else '' }."
    if fail_count > 0:
        final_message += f" Failed to archive {fail_count} email{ 's' if fail_count != 1 else '' }."
    
    response_data = {
        "success": overall_success,
        "message": final_message,
        "details": {
            "archive_errors": errors
        }
    }
    status_code = 200 if overall_success else 500
    
    return jsonify(response_data), status_code

# --- End New Route --- 