import os
import json
import base64
import functions_framework
from flask import jsonify, request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask_cors import CORS

@functions_framework.http
def scan_handler(request):
    """Handle scanning emails for unsubscribe links."""
    # Enable CORS for all routes
    if request.method == 'OPTIONS':
        # Handle preflight request
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }

    try:
        # Parse token data from request
        token_data = json.loads(request.get_data().decode('utf-8'))
        
        # Create Google API service
        gmail_service = create_gmail_service(token_data)
        if not gmail_service:
            return jsonify({'error': 'Failed to create Gmail service'}), 401, headers
        
        # Get query parameters (can be empty for default)
        query = request.args.get('query', '')
        max_results = int(request.args.get('max_results', '100'))
        
        # Scan emails
        unsub_data = scan_emails_for_unsubscribe(gmail_service, query, max_results)
        
        return jsonify(unsub_data), 200, headers
    except Exception as e:
        return jsonify({'error': str(e)}), 500, headers

def create_gmail_service(token_data):
    """Create and return a Gmail API service instance from token data."""
    try:
        # Create credentials from token data
        credentials = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes')
        )
        
        # Create Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        return service
    except Exception as e:
        print(f"Error creating Gmail service: {e}")
        return None

def scan_emails_for_unsubscribe(service, query='', max_results=100):
    """Scan emails for List-Unsubscribe headers."""
    results = []
    next_page_token = None
    count = 0
    
    try:
        # Keep fetching pages until we hit our max or run out of messages
        while count < max_results:
            # Get a batch of messages (just IDs first)
            request = service.users().messages().list(
                userId='me', 
                q=query,
                maxResults=min(max_results - count, 100),  # Adjust batch size
                pageToken=next_page_token
            )
            message_list = request.execute()
            
            # If no messages, break
            if 'messages' not in message_list:
                break
                
            # Process each message in this batch
            for msg_ref in message_list['messages']:
                # Get full message details
                msg = service.users().messages().get(userId='me', id=msg_ref['id'], format='full').execute()
                
                # Extract headers
                headers = {header['name'].lower(): header['value'] 
                          for header in msg.get('payload', {}).get('headers', [])
                          if 'name' in header and 'value' in header}
                
                # Check for List-Unsubscribe header
                if 'list-unsubscribe' in headers:
                    unsub_value = headers['list-unsubscribe']
                    
                    # Extract any HTTP link from the value
                    http_link = extract_http_link(unsub_value)
                    
                    if http_link:
                        # This email has a valid unsubscribe link
                        email_data = {
                            'id': msg['id'],
                            'threadId': msg['threadId'],
                            'unsubscribe_link': http_link,
                            'subject': headers.get('subject', 'No Subject'),
                            'from': headers.get('from', 'Unknown Sender'),
                            'date': headers.get('date', '')
                        }
                        results.append(email_data)
                
                count += 1
                if count >= max_results:
                    break
            
            # Check if there are more pages
            next_page_token = message_list.get('nextPageToken')
            if not next_page_token:
                break
                
    except Exception as e:
        print(f"Error scanning emails: {e}")
        # Return partial results if we have any
        
    return {
        'count': len(results),
        'emails': results
    }

def extract_http_link(unsubscribe_header):
    """Extract HTTP(S) link from List-Unsubscribe header.
    
    The header can have different formats:
    - <http://example.com/unsub>
    - <mailto:unsub@example.com>, <http://example.com/unsub>
    - http://example.com/unsub (no angle brackets)
    """
    # First, look for HTTP(S) URLs in angle brackets
    if '<http' in unsubscribe_header:
        parts = unsubscribe_header.split(',')
        for part in parts:
            part = part.strip()
            if part.startswith('<http') and part.endswith('>'):
                # Return the URL without angle brackets
                return part[1:-1]
    
    # If no HTTP link in angle brackets, check if the whole value is an HTTP URL
    elif unsubscribe_header.strip().startswith('http'):
        return unsubscribe_header.strip()
    
    # No HTTP link found
    return None 