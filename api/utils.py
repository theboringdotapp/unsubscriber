import os
import pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from flask import session, flash

# Note: We need access to SCOPES, REDIRECT_URI defined in index.py
# We also need the 'app' context implicitly for session/flash, 
# or explicitly pass app/config if needed. Flask handles context with Blueprints.

# Assuming SCOPES is available via import or config
# from . import SCOPES # Example if defined in __init__.py, adjust as needed

# --- Token Handling Modification for Vercel ---
# Vercel's filesystem is ephemeral for serverless functions.
# Storing tokens in session is a simple way for demo purposes, but has limitations.
# A more robust solution would use a database or secure external storage.

def save_credentials(creds):
    """Saves credentials to the session."""
    print("--- DEBUG: save_credentials: Attempting to save... ---") # Keep debug for now
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
        return None 

    print(f"--- DEBUG: get_gmail_service: Credentials loaded. Valid: {creds.valid}, Expired: {creds.expired}, Has Refresh Token: {bool(creds.refresh_token)} ---")

    if not creds.valid:
        print("--- DEBUG: get_gmail_service: Credentials are not valid. Checking refresh token... ---")
        if creds.expired and creds.refresh_token:
            print("--- DEBUG: get_gmail_service: Credentials expired and refresh token exists. Attempting refresh... ---")
            try:
                creds.refresh(Request())
                print("--- DEBUG: get_gmail_service: Token refreshed successfully. Saving new credentials. ---")
                save_credentials(creds) 
            except Exception as e:
                flash(f"Error refreshing credentials: {e}. Please re-authenticate.", "error")
                print(f"--- DEBUG: get_gmail_service: Token refresh FAILED: {e} ---")
                clear_credentials() 
                return None 
        else:
            print("--- DEBUG: get_gmail_service: Credentials invalid/expired OR no refresh token. Clearing credentials and returning None. ---")
            clear_credentials() 
            return None 

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
        
def has_modify_scope():
    """Check if the current user's credentials include the modify scope."""
    creds = load_credentials()
    if not creds:
        return False
        
    # Check if the modify scope is included in the scopes
    modify_scope = 'https://www.googleapis.com/auth/gmail.modify'
    
    # Print current scopes for debugging
    print(f"--- DEBUG: has_modify_scope: User has these scopes: {creds.scopes} ---")
    
    if hasattr(creds, 'scopes') and isinstance(creds.scopes, list):
        return modify_scope in creds.scopes
    return False