import os
import base64
import email
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText
from flask import Blueprint, redirect, url_for, request, session, flash, render_template
from googleapiclient.discovery import build # Needed?

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

    try:
        print("Fetching email page.")
        max_scan_emails = config.MAX_SCAN_EMAILS # Get constant from config

        if MOCK_API:
             list_response = _get_mock_message_list(page_token=page_token)
        else:
            list_response = service.users().messages().list(
                userId='me', maxResults=20, pageToken=page_token, q='unsubscribe'
            ).execute()

        messages = list_response.get('messages', [])
        if not messages: print("No messages found on this page.")
        else:
            for message_stub in messages:
                msg_id = message_stub['id']
                if MOCK_API:
                    full_message = _get_mock_message_details(msg_id)
                else:
                    full_message = service.users().messages().get(
                        userId='me', id=msg_id, format='metadata',
                        metadataHeaders=['List-Unsubscribe', 'From', 'Subject']
                    ).execute()
                unsubscribe_link, link_type = find_unsubscribe_links(full_message)
                if unsubscribe_link:
                    headers = full_message.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                    if '<' in sender and '>' in sender:
                        clean_sender = sender[:sender.find('<')].strip().replace('"', '') or sender[sender.find('<')+1:sender.find('>')]
                    else: clean_sender = sender
                    email_data = {"link": unsubscribe_link, "type": link_type, "full_sender": sender, "subject": subject, "message_id": msg_id}
                    if clean_sender not in found_subscriptions: found_subscriptions[clean_sender] = [email_data]
                    else: found_subscriptions[clean_sender].append(email_data)
        
        next_page_token = list_response.get('nextPageToken')
        print(f"--- SCAN ROUTE: Next page token from API: {next_page_token} ---")
        print(f"Scan finished for this page. Found {len(found_subscriptions)} unique senders on this page.")

    except Exception as e:
        flash(f"An error occurred during email scan: {e}", "error")
        print(f"!!! ERROR during scan loop: {e} !!!")
        return render_template('scan_results.html', emails=found_subscriptions, error=str(e), authenticated=authenticated, current_page_token=page_token, next_page_token=next_page_token)

    if not found_subscriptions and not page_token:
        flash("No emails with unsubscribe links found in the initial scan.", "info")

    return render_template('scan_results.html', emails=found_subscriptions, authenticated=authenticated, current_page_token=page_token, next_page_token=next_page_token)

@scan_bp.route('/unsubscribe', methods=['POST'])
def unsubscribe_and_archive():
    """Handles the unsubscribe action from the form (visiting link/sending email)."""
    service = utils.get_gmail_service()
    if not service:
        if request.headers.get('HX-Request') == 'true':
            return render_unsubscribe_modal_content(success=False, message="Authentication required. Please refresh and log in again."), 401
        else:
            flash("Authentication required.", "warning")
            return redirect(url_for('auth.login')) # Redirect to auth blueprint

    is_ajax = request.headers.get('HX-Request') == 'true'
    # ... (rest of implementation as before, using utils.get_gmail_service) ...
    final_ids_str = request.form.get('final_email_ids')
    final_links_str = request.form.get('final_unsubscribe_links')
    should_archive = request.form.get('should_archive') == 'true'
    if not final_ids_str or not final_links_str:
         if is_ajax: return render_unsubscribe_modal_content(success=False, message="Missing email IDs or links."), 400
         else: flash("Missing info.", "error"); return redirect(url_for('.scan_emails')) # Relative BP redirect
    ids = final_ids_str.split(',')
    links_raw = final_links_str.split(',,,,,')
    message_id = ids[0] if ids else None # Still processing first only
    link_type, link, sender = None, None, "Selected Email"
    if message_id:
         try:
            full_message = service.users().messages().get(userId='me', id=message_id, format='metadata', metadataHeaders=['List-Unsubscribe', 'From']).execute()
            link, link_type = find_unsubscribe_links(full_message)
            # ... (get sender name) ...
            headers = full_message.get('payload', {}).get('headers', [])
            sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'), sender)
            if '<' in sender_raw and '>' in sender_raw: sender = sender_raw[:sender_raw.find('<')].strip().replace('"', '') or sender_raw
            else: sender = sender_raw
         except Exception as fetch_err:
             print(f"Error fetching msg {message_id}: {fetch_err}")
             if is_ajax: return render_unsubscribe_modal_content(success=False, message=f"Could not retrieve details for message."), 500
             else: flash(f"Could not retrieve details.", "error"); return redirect(url_for('.scan_emails'))
    if not link or not link_type or not message_id:
         if is_ajax: return render_unsubscribe_modal_content(success=False, message="Missing link/type/ID after re-fetch."), 400
         else: flash("Missing info after re-fetch.", "error"); return redirect(url_for('.scan_emails'))
    print(f"--- UNSUBSCRIBE ACTION (ID: {message_id}) ...")
    success, error_message, http_link_for_modal = False, None, None
    try:
        if link_type == 'header_http':
            http_link_for_modal = link
            if should_archive: service.users().messages().modify(userId='me', id=message_id, body={'removeLabelIds': ['INBOX']}).execute()
            success = True
        elif link_type == 'header_mailto':
            parsed_mailto = urlparse(link); to_address = parsed_mailto.path; params = parse_qs(parsed_mailto.query)
            subject = params.get('subject', ['Unsubscribe'])[0]; body = params.get('body', ['Please unsubscribe me.'])[0]
            if not to_address: raise ValueError("Mailto link missing recipient.")
            message = MIMEText(body); message['to'] = to_address; message['subject'] = subject
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message_body = {'raw': raw_message}
            if MOCK_API:
                print("--- MOCK SEND EMAIL ---")
            else:
                service.users().messages().send(userId='me', body=send_message_body).execute()
            if should_archive: service.users().messages().modify(userId='me', id=message_id, body={'removeLabelIds': ['INBOX']}).execute()
            success = True
    except Exception as e: error_message = f"Error processing unsubscribe for {sender}: {e}"; print(f"!!! ERROR: {error_message} !!!")
    if is_ajax:
        if success:
            archive_msg = " Email archived." if should_archive else " Email kept."
            modal_msg = f"Unsubscribe sent for {sender}.{archive_msg}" if link_type == 'header_mailto' else f"Processed archive for {sender}.{archive_msg}"
            return render_unsubscribe_modal_content(success=True, message=modal_msg, http_link=http_link_for_modal)
        else: return render_unsubscribe_modal_content(success=False, message=error_message or "Unknown error.")
    else:
        if success:
             if link_type == 'header_http': session['unsubscribe_success'] = f"Redirecting... Email { 'archived' if should_archive else 'kept'}."; return redirect(link)
             else: flash(f"Email sent for {sender}! Email { 'archived' if should_archive else 'kept'}.", "success")
        else: flash(error_message, "error") # Flash error only if non-AJAX
        return redirect(url_for('index')) 