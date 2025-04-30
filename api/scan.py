import os
import re
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
    if utils.should_log(): print("--- USING MOCK MESSAGE LIST ---")
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
    if utils.should_log(): print(f"--- USING MOCK MESSAGE DETAILS FOR ID: {msg_id} ---")
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
    """Parses email headers for unsubscribe links with enhanced header support."""
    unsubscribe_info = {"header_link": None, "mailto_link": None}
    try:
        headers = message_data.get('payload', {}).get('headers', [])
        
        # Define the headers to check (in priority order)
        unsubscribe_headers = [
            'list-unsubscribe',
            'x-list-unsubscribe',
            'list-unsubscribe-post'  # Sometimes contains different links
        ]
        
        # First pass: Check standard unsubscribe headers
        for header_name in unsubscribe_headers:
            for header in headers:
                if header['name'].lower() == header_name:
                    value = header['value']
                    parse_unsubscribe_header_value(value, unsubscribe_info)
                    # If we found an HTTP link, we can break early
                    if unsubscribe_info["header_link"]:
                        break
        
        # If no link found, check message body for common patterns (snippet in metadata)
        if not unsubscribe_info["header_link"] and not unsubscribe_info["mailto_link"]:
            # Try to extract from List-ID or other headers
            list_id = None
            
            for header in headers:
                if header['name'].lower() == 'list-id':
                    list_id = header['value']
            
            # Future enhancement: construct unsubscribe URLs for known ESPs
    
    except Exception as e:
        print(f"Error parsing message for unsubscribe link: {e}")

    # Return links in order of preference
    if unsubscribe_info["header_link"]: 
        return unsubscribe_info["header_link"], "header_http"
    elif unsubscribe_info["mailto_link"]: 
        return unsubscribe_info["mailto_link"], "header_mailto"
    else: 
        return None, None

def parse_unsubscribe_header_value(value, unsubscribe_info):
    """Helper function to parse unsubscribe header values."""
    for part in value.split(','):
        part = part.strip()
        link = None
        
        # Check for mailto link in brackets
        if '<mailto:' in part:
            start = part.find('<') + 1
            end = part.find('>')
            if start < end:
                link = part[start:end]
                unsubscribe_info["mailto_link"] = link
        
        # Check for http link in brackets
        elif '<http' in part:
            start = part.find('<') + 1
            end = part.find('>')
            if start < end:
                link = part[start:end]
                # Prefer HTTPS over HTTP links
                if not unsubscribe_info["header_link"] or link.startswith('https'):
                    unsubscribe_info["header_link"] = link
        
        # Check for bare http link
        elif part.strip().startswith('http'):
            link = part.strip()
            # Prefer HTTPS over HTTP links
            if not unsubscribe_info["header_link"] or link.startswith('https'):
                unsubscribe_info["header_link"] = link
        
        # Check for bare mailto link
        elif part.strip().startswith('mailto:'):
            link = part.strip()
            unsubscribe_info["mailto_link"] = link

def render_unsubscribe_modal_content(success=True, message="", http_link=None):
    """Renders an HTML snippet for the unsubscribe result modal."""
    if success:
        status_message = message or "Request processed successfully!"
        link_message = ""
        if http_link:
             link_message = f'<p class="text-sm mt-2 text-muted-foreground">You may need to <a href="{http_link}" target="_blank" class="text-brand hover:underline">visit the unsubscribe link</a> manually.</p>'
        html = f"""
        <div class="text-center p-6 flex flex-col items-center">
            <div class="checkmark-container mb-4">
                <svg class="checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                    <circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none"/>
                    <path class="checkmark-check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
                </svg>
            </div>
            <h3 class="text-xl font-semibold text-success mb-2">Success!</h3>
            <p class="text-foreground">{status_message}</p>
            {link_message}
            <button class="mt-6 btn btn-primary btn-md focus-ring w-full" onclick="window.removeProcessedEmails()">Done</button>
        </div>
        """
    else:
        status_message = message or "An error occurred."
        html = f"""
        <div class="bg-background rounded-lg p-6 text-center flex flex-col items-center">
            <div class="error-container mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-destructive" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
            </div>
            <h3 class="text-xl font-semibold text-destructive mb-2">Error</h3>
            <p class="text-muted-foreground">{status_message}</p>
            <button class="mt-4 btn btn-secondary focus-ring" onclick="window.closeErrorMessage()">Close</button>
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
    if utils.should_log(): print("--- SCAN ROUTE START ---")
    page_token = request.args.get('token', None)
    if utils.should_log(): print(f"--- SCAN ROUTE: Received page token: {page_token} ---")
    
    # Store the current page token if we're on a scan page
    # This will be used when returning after permission upgrade
    if page_token:
        session['return_to_scan_token'] = page_token
        if utils.should_log(): print(f"Storing current scan token: {page_token} for possible return after permission upgrade")
    
    # Check if archive feature was just enabled
    archive_enabled = request.args.get('archive_enabled') == 'true'
    if utils.should_log(): print(f"--- SCAN ROUTE: Archive just enabled: {archive_enabled} ---")

    service = utils.get_gmail_service()
    if not service:
        flash("Authentication required.", "warning")
        if utils.should_log(): print("Scan route: Not authenticated.")
        return redirect(url_for('auth.login')) # Redirect to auth blueprint login
    
    authenticated = True 
    found_subscriptions = {} 
    next_page_token = None 
    
    # Check if user has archive permissions
    if utils.should_log(): print("--- SCAN ROUTE: Checking archive permission... ---")
    has_archive_permission = utils.has_modify_scope()
    if utils.should_log(): print(f"--- SCAN ROUTE: Result of has_modify_scope check: {has_archive_permission} ---")
    
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
        if utils.should_log(): print("Fetching email page.")
        max_scan_emails = config.MAX_SCAN_EMAILS # Get constant from config

        if MOCK_API:
             list_response = _get_mock_message_list(page_token=page_token)
        else:
            # Combine specific header search with keyword fallback
            keyword_query = ' OR '.join(config.UNSUBSCRIBE_SEARCH_TERMS)
            combined_query = f"has:list-unsubscribe OR ({keyword_query})"
            if utils.should_log(): print(f"--- SCAN ROUTE: Using combined query: {combined_query} ---")

            list_response = service.users().messages().list(
                userId='me',
                maxResults=20,
                pageToken=page_token,
                q=combined_query, # Use the combined query
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
                            # Add more unsubscribe-related headers to check
                            metadataHeaders=[
                                'List-Unsubscribe', 'List-Unsubscribe-Post', 'From', 'Subject',
                                'X-List-Unsubscribe', 'List-Id', 'Feedback-ID'
                            ] 
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
        if utils.should_log(): print(f"--- SCAN ROUTE: Next page token from API: {next_page_token} ---")
        if utils.should_log(): print(f"Scan finished for this page. Found {len(found_subscriptions)} unique senders on this page.")

    except Exception as e:
        flash(f"An error occurred during email scan: {e}", "error")
        print(f"!!! ERROR during scan loop: {e} !!!")
        # Pass colors, archive permission, and config here too
        return render_template('scan_results.html', 
                          subscriptions=found_subscriptions, 
                          error=str(e), 
                          authenticated=authenticated, 
                          current_page_token=page_token, 
                          next_page_token=next_page_token, 
                          colors=colors,
                          has_archive_permission=has_archive_permission,
                          config=config)

    if not found_subscriptions and not page_token:
        flash("No emails with unsubscribe links found in the initial scan.", "info")

    # Pass colors, archive permission, and config to the template context
    return render_template('scan_results.html', 
                          subscriptions=found_subscriptions, 
                          authenticated=authenticated, 
                          current_page_token=page_token, 
                          next_page_token=next_page_token, 
                          colors=colors,
                          has_archive_permission=has_archive_permission,
                          config=config)

@scan_bp.route('/unsubscribe', methods=['POST'])
def unsubscribe_and_archive():
    """Handles the unsubscribe action from the form. 
    Optimized to focus on mailto links only, as HTTP links are handled client-side."""
    service = utils.get_gmail_service()
    if not service:
        return jsonify({"success": False, "error": "Authentication required. Please refresh and log in again."}), 401

    # Get data from form POST
    email_ids = request.form.getlist('email_ids')
    should_archive = request.form.get('archive') == 'true'
    
    if not email_ids:
        return jsonify({"success": False, "error": "Missing email IDs."}), 400
        
    if utils.should_log(): print(f"--- UNSUBSCRIBE ACTION for {len(email_ids)} emails, Archive: {should_archive} ---")
    
    # We'll process unsubscribe actions per sender to avoid duplicates
    processed_senders = set()
    unsubscribe_actions = [] # List of tuples: (email_id, link_type, link, sender)
    emails_to_archive = set(email_ids) if should_archive else set()
    
    # Map to store email IDs by sender
    sender_email_map = {}
    
    # Step 1: First pass to organize emails by sender
    if utils.should_log(): print(f"Organizing {len(email_ids)} emails by sender")
    
    # Process in batches to reduce API calls - batch size of 10
    batch_size = 10
    for i in range(0, len(email_ids), batch_size):
        batch_ids = email_ids[i:i+batch_size]
        
        for msg_id in batch_ids:
            try:
                # Get minimal metadata - just the From header
                full_message = service.users().messages().get(
                    userId='me', 
                    id=msg_id, 
                    format='metadata', 
                    metadataHeaders=['From']
                ).execute()
                
                headers = full_message.get('payload', {}).get('headers', [])
                sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                
                # Clean up sender name for grouping and display
                if '<' in sender_raw and '>' in sender_raw:
                    display_sender = sender_raw[:sender_raw.find('<')].strip().replace('"', '')
                    if not display_sender:
                        # Use email part if name is empty
                        email_part = sender_raw[sender_raw.find('<')+1:sender_raw.find('>')]
                        display_sender = email_part if email_part else sender_raw
                else:
                    display_sender = sender_raw
                
                # Store this email ID under its sender
                if display_sender not in sender_email_map:
                    sender_email_map[display_sender] = []
                
                sender_email_map[display_sender].append(msg_id)
                
            except Exception as e:
                print(f"Error getting sender for email {msg_id}: {e}")
    
    # Step 2: Find unsubscribe links from the first email for each sender
    if utils.should_log(): print(f"Found {len(sender_email_map)} unique senders")
    
    for sender, sender_email_ids in sender_email_map.items():
        if not sender_email_ids:
            continue
            
        # Use the first email from this sender to check for unsubscribe link
        first_email_id = sender_email_ids[0]
        
        try:
            # Get unsubscribe headers for this email
            full_message = service.users().messages().get(
                userId='me', 
                id=first_email_id, 
                format='metadata', 
                metadataHeaders=[
                    'List-Unsubscribe', 'X-List-Unsubscribe', 'List-Unsubscribe-Post'
                ]
            ).execute()
            
            link, link_type = find_unsubscribe_links(full_message)
            
            # We're only interested in mailto links here, as HTTP links are handled client-side
            if link and link_type == 'header_mailto':
                unsubscribe_actions.append((first_email_id, link_type, link, sender))
                
        except Exception as e:
            print(f"Error finding unsubscribe link for sender {sender} (email {first_email_id}): {e}")
    
    # We no longer process mailto links automatically
    # Instead we'll save them for the user to handle manually
    if utils.should_log(): print(f"Found {len(unsubscribe_actions)} mailto unsubscribe links")
    
    # We'll collect these links to display to the user in the UI
    # No automatic processing is done with the readonly scope
    mailto_links = []
    
    for idx, (msg_id, link_type, link, sender) in enumerate(unsubscribe_actions):
        try:
            if utils.should_log(): print(f"Found mailto link for {sender}: {link}")
            
            # Parse mailto to get details to show to the user
            parsed_mailto = urlparse(link)
            to_address = parsed_mailto.path
            params = parse_qs(parsed_mailto.query)
            subject = params.get('subject', ['Unsubscribe'])[0]
            body = params.get('body', ['Please unsubscribe me.'])[0]
            
            if not to_address:
                print(f"Warning: Mailto link missing recipient for {sender}")
                continue
                
            # Add to the list of links to show in the UI
            mailto_links.append({
                'sender': sender,
                'message_id': msg_id,
                'email': to_address,
                'subject': subject,
                'body': body,
                'link': link
            })
            
        except Exception as e:
            error_detail = f"Failed to parse mailto link for {sender}: {e}"
            print(f"ERROR: {error_detail}")
    
    # We don't have success/fail counts or processed IDs anymore
    # since we're not automatically sending emails
    successfully_processed_ids = []
    
    # Step 4: Archive emails if requested (now handled client-side in a separate request)
    # Batch archive is now done in a separate endpoint call to optimize cloud function usage
    
    # Construct response for UI display (no processing with readonly scope)
    
    if utils.should_log(): print(f"Found {len(mailto_links)} mailto links for manual handling")
    
    final_message = f"Found {len(mailto_links)} email{'s' if len(mailto_links) != 1 else ''} with mailto: unsubscribe links."
    
    response_data = {
        "success": True,
        "message": final_message,
        "details": {
            "mailto_links": mailto_links,
            "found_count": len(mailto_links)
        },
        "http_link": None  # No HTTP link needed here as they're handled client-side
    }

    status_code = 200 # Always success as we're just finding links, not processing
    return jsonify(response_data), status_code

# --- Optimized Route for Batch Archiving --- 
@scan_bp.route('/archive', methods=['POST'])
def archive_emails():
    """Archives selected emails by removing the INBOX label if user has permission.
    Otherwise informs users this requires modify permission."""
    if utils.should_log(): print("--- ARCHIVE ROUTE CALLED ---")
    
    # Get data from form POST
    email_ids = request.form.getlist('email_ids')
    
    if not email_ids:
        return jsonify({"success": False, "error": "Missing email IDs."}), 400
        
    if utils.should_log(): print(f"--- ARCHIVE ACTION for {len(email_ids)} emails ---")
    
    # Check if user has archive permissions
    if utils.has_modify_scope():
        # User has the necessary permissions, perform archive
        service = utils.get_gmail_service()
        if not service:
            return jsonify({"success": False, "error": "Authentication required."}), 401
            
        # We have permission and authentication - process the archive request
        try:
            batch = service.new_batch_http_request()
            
            # Track which IDs were successfully archived
            archived_ids = []
            archive_errors = []
            
            # Use a batch request for efficiency
            for idx, msg_id in enumerate(email_ids):
                try:
                    # Add to batch - modify labels by removing INBOX
                    batch.add(
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={'removeLabelIds': ['INBOX']}
                        ),
                        request_id=f'archive_{idx}'
                    )
                    archived_ids.append(msg_id)
                except Exception as e:
                    print(f"Error adding message {msg_id} to batch: {e}")
                    archive_errors.append(f"Error adding message {msg_id} to batch: {e}")
            
            # Execute the batch request
            if utils.should_log(): print(f"Executing batch archive for {len(email_ids)} emails...")
            batch.execute()
            
            response_data = {
                "success": True,
                "message": f"Successfully archived {len(archived_ids)} emails.",
                "details": {
                    "archived_ids": archived_ids,
                    "archive_errors": archive_errors
                }
            }
            
            return jsonify(response_data), 200
            
        except Exception as e:
            error_message = f"Error during batch archive operation: {e}"
            print(f"ARCHIVE ERROR: {error_message}")
            return jsonify({
                "success": False,
                "error": error_message,
                "message": "Archive operation failed due to a technical error.",
                "details": {
                    "archive_errors": [str(e)]
                }
            }), 500
    else:
        # Inform the user that they don't have the necessary permission for archiving
        response_data = {
            "success": False,
            "message": "Archiving emails requires additional permissions. The application is currently using read-only access.",
            "details": {
                "reason": "The application is using the gmail.readonly scope which doesn't allow modifying emails.",
                "solution": "Users will need to manually archive emails in Gmail.",
                "permission_required": "https://www.googleapis.com/auth/gmail.modify",
                "help_text": "To archive emails, please select them in Gmail and use the archive button."
            }
        }
        
        return jsonify(response_data), 403  # HTTP 403 Forbidden - correct status code for permission issues

# --- End Optimized Route --- 