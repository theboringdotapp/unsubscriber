import os
import json
import requests
import functions_framework
from flask import jsonify, request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask_cors import CORS

@functions_framework.http
def unsubscribe_handler(request):
    """Handle unsubscribing from emails and archiving them."""
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
        # Parse request data
        request_data = json.loads(request.get_data().decode('utf-8'))
        token_data = request_data.get('token')
        selected_emails = request_data.get('selected_emails', [])
        
        if not token_data or not selected_emails:
            return jsonify({'error': 'Missing token or selected emails'}), 400, headers
        
        # Create Gmail service
        gmail_service = create_gmail_service(token_data)
        if not gmail_service:
            return jsonify({'error': 'Failed to create Gmail service'}), 401, headers
        
        # Process each email
        results = []
        for email in selected_emails:
            email_id = email.get('id')
            unsubscribe_link = email.get('unsubscribe_link')
            
            if not email_id or not unsubscribe_link:
                results.append({
                    'id': email_id or 'unknown',
                    'unsubscribe_success': False,
                    'archive_success': False,
                    'error': 'Missing email ID or unsubscribe link'
                })
                continue
                
            # Process this email
            result = process_email(gmail_service, email_id, unsubscribe_link)
            results.append(result)
        
        return jsonify({'results': results}), 200, headers
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

def process_email(service, email_id, unsubscribe_link):
    """Attempt to unsubscribe and archive a single email."""
    result = {
        'id': email_id,
        'unsubscribe_success': False,
        'archive_success': False
    }
    
    try:
        # 1. Visit the unsubscribe link
        unsub_response = requests.get(
            unsubscribe_link,
            timeout=10,  # Timeout after 10 seconds
            allow_redirects=True,  # Follow redirects
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        )
        
        # Consider success if status code is 2xx or 3xx
        result['unsubscribe_success'] = 200 <= unsub_response.status_code < 400
        result['unsubscribe_status_code'] = unsub_response.status_code
        
        # 2. Archive the email (remove INBOX label)
        try:
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            result['archive_success'] = True
        except Exception as e:
            result['archive_error'] = str(e)
    
    except requests.RequestException as e:
        result['unsubscribe_error'] = str(e)
    except Exception as e:
        result['error'] = str(e)
    
    return result 