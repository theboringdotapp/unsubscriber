import os
import re
import base64
import email
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText
from flask import Blueprint, redirect, url_for, request, session, flash, render_template, jsonify
from googleapiclient.discovery import build # Needed?
from datetime import datetime # Add datetime import
from googleapiclient.http import BatchHttpRequest # Import BatchHttpRequest

# Import utils and constants
from . import utils
from . import config # Import config directly

# Add url_prefix to the blueprint
scan_bp = Blueprint('scan', __name__, url_prefix='/scan')

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
    """Parses email for unsubscribe links from headers and body"""
    unsubscribe_info = {
        "header_link": None, 
        "mailto_link": None,
        "body_link": None,  # New field for body links
        "body_link_score": 0  # Score to prioritize better body links
    }
    
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
        
        # Always parse body for links, regardless of whether we found header links
        try:
            # Get message body parts
            parts = message_data.get('payload', {}).get('parts', [])
            if not parts and message_data.get('payload'):
                parts = [message_data.get('payload')]
                
            for part in parts:
                if part.get('mimeType') == 'text/html':
                    # Get and decode body data
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body_html = base64.urlsafe_b64decode(data).decode('utf-8')
                        
                        # More comprehensive search for unsubscribe links with context
                        # First look for links with unsubscribe text in the anchor text itself
                        unsubscribe_anchors = re.findall(r'<a\s+[^>]*href=["\'](https?://[^"\']+)["\'][^>]*>([^<]+)</a>', body_html, re.IGNORECASE)
                        
                        best_score = 0
                        best_link = None
                        
                        # Check anchor text links first
                        for url, anchor_text in unsubscribe_anchors:
                            score = 0
                            anchor_lower = anchor_text.lower()
                            
                            # Score based on anchor text quality
                            if 'unsubscribe' in anchor_lower:
                                score += 10
                            elif 'opt out' in anchor_lower or 'opt-out' in anchor_lower:
                                score += 8
                            elif 'cancel' in anchor_lower and ('subscription' in anchor_lower or 'newsletter' in anchor_lower):
                                score += 7
                            elif 'preferences' in anchor_lower or 'manage' in anchor_lower:
                                score += 5
                            
                            # Score based on URL quality
                            url_lower = url.lower()
                            if 'unsubscribe' in url_lower:
                                score += 5
                            elif 'opt-out' in url_lower or 'optout' in url_lower:
                                score += 4
                            elif 'preference' in url_lower:
                                score += 3
                                
                            # Penalize likely webhook or tracking URLs
                            if 'webhook' in url_lower or 'callback' in url_lower or 'track' in url_lower:
                                score -= 5
                            
                            # If this link is better than what we've found so far
                            if score > best_score:
                                best_score = score
                                best_link = url
                        
                        # If we didn't find a good link with anchor text, try the older regex patterns
                        if best_score < 5:
                            unsubscribe_patterns = [
                                r'href=["\'](https?://[^"\']*unsubscribe[^"\']*)["\']',
                                r'href=["\'](https?://[^"\']*opt.?out[^"\']*)["\']',
                                r'href=["\'](https?://[^"\']*preferences[^"\']*)["\']'
                            ]
                            
                            for pattern in unsubscribe_patterns:
                                matches = re.findall(pattern, body_html, re.IGNORECASE)
                                if matches:
                                    best_link = matches[0]
                                    best_score = 2  # Lower priority than anchor text links
                                    break
                        
                        # Update body link if we found a good one
                        if best_link and best_score > 0:
                            unsubscribe_info["body_link"] = best_link
                            unsubscribe_info["body_link_score"] = best_score
        except Exception as e:
            print(f"Error parsing body for unsubscribe link: {e}")
            
    except Exception as e:
        print(f"Error parsing message for unsubscribe link: {e}")

    # Remove the primary link selection logic
    # Return the dictionary containing all found link types
    return unsubscribe_info

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

@scan_bp.route('/emails', methods=['GET'])
def scan_emails():
    """Scans recent emails for unsubscribe links, supporting pagination.
    Uses batching to fetch email details efficiently."""
    if utils.should_log(): print("--- SCAN ROUTE START (Batching Enabled) ---")
    page_token = request.args.get('token', None)
    if utils.should_log(): print(f"--- SCAN ROUTE: Received page token: {page_token} ---")
    
    if page_token:
        session['return_to_scan_token'] = page_token
        if utils.should_log(): print(f"Storing current scan token: {page_token} for possible return")
    
    archive_enabled = request.args.get('archive_enabled') == 'true'
    if utils.should_log(): print(f"--- SCAN ROUTE: Archive just enabled: {archive_enabled} ---")

    service = utils.get_gmail_service()
    if not service:
        flash("Authentication required.", "warning")
        if utils.should_log(): print("Scan route: Not authenticated.")
        return redirect(url_for('auth.login'))
    
    authenticated = True 
    found_subscriptions = {} 
    next_page_token = None 
    
    if utils.should_log(): print("--- SCAN ROUTE: Checking archive permission... ---")
    has_archive_permission = utils.has_modify_scope()
    if utils.should_log(): print(f"--- SCAN ROUTE: Result of has_modify_scope check: {has_archive_permission} ---")
    
    colors = config.SENDER_COLORS # Get colors from config

    try:
        if utils.should_log(): print("Fetching email list page.")
        max_scan_emails = config.MAX_SCAN_EMAILS # Get constant from config
        
        list_response = None
        messages = []
        
        if MOCK_API:
            list_response = _get_mock_message_list(page_token=page_token)
            messages = list_response.get('messages', [])
            next_page_token = list_response.get('nextPageToken')
        else:
            spanish_portuguese_terms = ['"cancelar suscripción"', '"desuscribirse"', '"darse de baja"', 
                                       '"cancelar inscrição"', '"descadastrar"', '"desinscrever"']
            all_search_terms = config.UNSUBSCRIBE_SEARCH_TERMS + spanish_portuguese_terms
            keyword_query = ' OR '.join(all_search_terms)
            combined_query = f"has:list-unsubscribe OR ({keyword_query})"
            if utils.should_log(): print(f"--- SCAN ROUTE: Using combined query: {combined_query} ---")

            list_response = service.users().messages().list(
                userId='me',
                maxResults=config.EMAILS_PER_PAGE, # Use config for page size
                pageToken=page_token,
                q=combined_query, 
                labelIds=['INBOX']
            ).execute()
            
            messages = list_response.get('messages', [])
            next_page_token = list_response.get('nextPageToken')

        if not messages: 
            print("No messages found on this page.")
        else:
            message_details = {} # To store results from batch
            batch_errors = {}    # To store errors from batch

            # Define the callback function for the batch request
            def batch_callback(request_id, response, exception):
                if exception:
                    # Handle error for this specific request
                    print(f"!!! BATCH ERROR fetching message {request_id}: {exception} !!!")
                    batch_errors[request_id] = str(exception)
                else:
                    # Store successful response
                    message_details[request_id] = response

            # Define the correct Gmail batch URI
            gmail_batch_uri = f"{service._baseUrl}/batch/gmail/v1"
            if utils.should_log(): print(f"--- SCAN ROUTE: Using Gmail Batch URI: {gmail_batch_uri} ---")
            
            # Create a batch request with the specific URI and callback
            batch = BatchHttpRequest(batch_uri=gmail_batch_uri, callback=batch_callback)
            
            # Add each message get request to the batch
            for message_stub in messages:
                msg_id = message_stub['id']
                if MOCK_API:
                    # If mocking, get details directly, bypass batch
                    full_message = _get_mock_message_details(msg_id)
                    full_message['internalDate'] = str(int(datetime.now().timestamp() * 1000)) # Mock date
                    message_details[msg_id] = full_message
                else:
                    batch.add(
                        service.users().messages().get(userId='me', id=msg_id, format='full'),
                        # callback=batch_callback, # Callback is now set during BatchHttpRequest init
                        request_id=msg_id # Use msg_id to map results easily
                    )
            
            # Execute the batch request if not mocking API
            if not MOCK_API and len(messages) > 0:
                 if utils.should_log(): print(f"--- SCAN ROUTE: Executing batch request for {len(messages)} emails ---")
                 try:
                     batch.execute(http=service._http) # Pass authenticated http object
                     if utils.should_log(): print(f"--- SCAN ROUTE: Batch execution finished. Errors: {len(batch_errors)}")
                 except Exception as batch_exec_error:
                      print(f"!!! FATAL BATCH EXECUTION ERROR: {batch_exec_error} !!!")
                      flash("A critical error occurred while fetching email details.", "error")
                      # Render template with error, potentially empty subscriptions
                      return render_template('scan_results.html', 
                                subscriptions={}, 
                                error=f"Batch fetch error: {batch_exec_error}", 
                                authenticated=authenticated, 
                                current_page_token=page_token, 
                                next_page_token=next_page_token, 
                                colors=colors,
                                has_archive_permission=has_archive_permission,
                                config=config)

            # Process the results collected by the batch callback (or directly if mocking)
            if utils.should_log(): print(f"--- SCAN ROUTE: Processing {len(message_details)} fetched email details ---")
            for msg_id, full_message in message_details.items():
                try: 
                    # Get the dictionary of links
                    unsubscribe_info = find_unsubscribe_links(full_message)
                    header_link = unsubscribe_info.get("header_link")
                    mailto_link = unsubscribe_info.get("mailto_link")
                    body_link = unsubscribe_info.get("body_link")

                    # Determine the primary link for display/initial action based on priority: header > mailto > body
                    primary_link = header_link or mailto_link or body_link

                    if primary_link: # Proceed if at least one type of link was found
                        headers = full_message.get('payload', {}).get('headers', [])
                        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                        
                        internal_date = full_message.get('internalDate', '0')
                        email_date_formatted = format_email_date(internal_date)
                        
                        # Determine clean sender name
                        if '<' in sender and '>' in sender:
                            clean_sender = sender[:sender.find('<')].strip().replace('"', '')
                            if not clean_sender:
                                start = sender.find('<') + 1; end = sender.find('>')
                                clean_sender = sender[start:end] if start < end else sender
                        else: 
                            clean_sender = sender
                        
                        email_data = {
                            "id": msg_id, 
                            "subject": subject, 
                            "date": email_date_formatted,
                            "full_sender": sender,
                            # Store all potential links
                            "header_link": header_link, 
                            "mailto_link": mailto_link, 
                            "body_link": body_link,
                            # Store the primary link determined for this specific email
                            "unsubscribe_link": primary_link 
                        }
                        
                        if clean_sender not in found_subscriptions:
                            found_subscriptions[clean_sender] = {
                                'emails': [email_data],
                                # Keep the first primary link found for the sender group 
                                # for display purposes in the header? Or maybe remove this top-level one.
                                # Let's remove it for now to avoid confusion. The link per email is more accurate.
                                # 'unsubscribe_link': primary_link 
                            }
                        else:
                            found_subscriptions[clean_sender]['emails'].append(email_data)
                            # Update sender group's primary link if a header link is found later? 
                            # No, keep it simple. Each email has its own links.
                            
                except Exception as msg_error:
                     # Log error processing a specific message after batch fetch
                     print(f"!!! ERROR processing message {msg_id} (post-batch): {msg_error} !!!")
                     # Continue processing other messages

        if utils.should_log(): print(f"--- SCAN ROUTE: Finished processing page. Found {len(found_subscriptions)} unique senders. Next token: {next_page_token} ---")

    except Exception as e:
        flash(f"An error occurred during email scan: {e}", "error")
        print(f"!!! ERROR during scan main try block: {e} !!!")
        # Pass colors, archive permission, and config here too
        return render_template('scan_results.html', 
                          subscriptions=found_subscriptions, # Might be partially populated
                          error=str(e), 
                          authenticated=authenticated, 
                          current_page_token=page_token, 
                          next_page_token=next_page_token, # Pass original next token if available
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
    Identifies mailto links for manual user action and prepares HTTP links for client-side processing."""
    service = utils.get_gmail_service()
    if not service:
        return jsonify({"success": False, "error": "Authentication required. Please refresh and log in again."}), 401

    # Get data from form POST
    email_ids = request.form.getlist('email_ids')
    # Get links associated with these IDs (sent from client)
    header_links = request.form.getlist('header_links') 
    body_links = request.form.getlist('body_links')
    mailto_links = request.form.getlist('mailto_links')
    
    should_archive = request.form.get('archive') == 'true'
    
    if not email_ids or len(email_ids) != len(header_links) or len(email_ids) != len(body_links) or len(email_ids) != len(mailto_links):
        return jsonify({"success": False, "error": "Missing or mismatched email data."}), 400
        
    if utils.should_log(): print(f"--- UNSUBSCRIBE ACTION for {len(email_ids)} emails, Archive: {should_archive} ---")
    
    emails_data = []
    for i in range(len(email_ids)):
        emails_data.append({
            "id": email_ids[i],
            "header_link": header_links[i] if header_links[i] != 'null' else None,
            "body_link": body_links[i] if body_links[i] != 'null' else None,
            "mailto_link": mailto_links[i] if mailto_links[i] != 'null' else None,
        })

    mailto_actions = []
    # We don't need sender grouping here anymore, as the client sends exact links per ID
    
    if utils.should_log(): print(f"Processing {len(emails_data)} emails for unsubscribe links")

    for email_data in emails_data:
        msg_id = email_data["id"]
        mailto_link = email_data["mailto_link"]
        
        # We only need to process mailto links on the backend for now
        if mailto_link:
             try:
                # Safer logging
                if utils.should_log(): print(f"Found mailto: unsubscribe link for message {msg_id}") 
                
                # Parse mailto to get details to show to the user
                parsed_mailto = urlparse(mailto_link)
                to_address = parsed_mailto.path
                params = parse_qs(parsed_mailto.query)
                subject = params.get('subject', ['Unsubscribe'])[0]
                body = params.get('body', ['Please unsubscribe me.'])[0]
                
                if not to_address:
                    print(f"Warning: Mailto link missing recipient for email {msg_id}")
                    continue
                    
                # Add to the list of links to show in the UI
                mailto_actions.append({
                    'message_id': msg_id,
                    'email': to_address,
                    'subject': subject,
                    'body': body,
                    'link': mailto_link # Keep original link
                    # Sender info is not readily available here without another API call, UI might need adjustment
                })
                
             except Exception as e:
                 error_detail = f"Failed to parse mailto link for email {msg_id}: {e}"
                 print(f"ERROR: {error_detail}")

    # We don't have success/fail counts or processed IDs anymore
    # since we're not automatically sending emails via mailto
    
    if utils.should_log(): print(f"Found {len(mailto_actions)} mailto links for manual handling")
    
    # Construct response for UI display
    # The message should reflect that HTTP links are intended for client-side processing
    
    http_link_count = sum(1 for e in emails_data if e["header_link"] or e["body_link"])
    
    message_parts = []
    if http_link_count > 0:
        message_parts.append(f"{http_link_count} HTTP unsubscribe request{'s' if http_link_count != 1 else ''} will be attempted.")
    if len(mailto_actions) > 0:
         message_parts.append(f"Found {len(mailto_actions)} mailto link{'s' if len(mailto_actions) != 1 else ''} requiring manual action.")
         
    if not message_parts:
        final_message = "No unsubscribe links found for selected emails."
    else:
        final_message = " ".join(message_parts)

    # The primary purpose of this endpoint now is to identify mailto links.
    # HTTP link processing confirmation will happen client-side.
    response_data = {
        "success": True, # Success means the backend processed the request, not that unsubscribes worked
        "message": final_message,
        "details": {
            "mailto_links": mailto_actions,
            "found_count": len(mailto_actions) # Only count mailto links found by backend
        },
        "http_link": None # No single HTTP link to return anymore
    }

    status_code = 200 
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