import os
import pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from flask import session, flash
from . import config # Import config

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
    if config.DEBUG_LOGGING: print("--- DEBUG: save_credentials: Attempting to save... ---") # Keep debug for now
    try:
        session['credentials'] = pickle.dumps(creds).decode('latin1') # Store pickled creds as string
        if config.DEBUG_LOGGING: print("--- DEBUG: save_credentials: Successfully pickled and stored credentials in session. ---")
    except Exception as e:
        if config.DEBUG_LOGGING: print(f"--- DEBUG: save_credentials: ERROR pickling/storing credentials: {e} ---")

def load_credentials():
    """Loads credentials from the session."""
    if config.DEBUG_LOGGING: print("--- DEBUG: load_credentials: Attempting to load credentials from session. ---")
    creds_pickle = session.get('credentials')
    if creds_pickle:
        if config.DEBUG_LOGGING: print("--- DEBUG: load_credentials: Found 'credentials' key in session. Attempting to unpickle. ---")
        try:
            creds = pickle.loads(creds_pickle.encode('latin1'))
            if config.DEBUG_LOGGING: print("--- DEBUG: load_credentials: Successfully unpickled credentials. ---")
            return creds
        except Exception as e:
            if config.DEBUG_LOGGING: print(f"--- DEBUG: load_credentials: ERROR unpickling credentials: {e} ---")
            # Optionally clear the corrupted session data
            session.pop('credentials', None)
            return None
    else:
        if config.DEBUG_LOGGING: print("--- DEBUG: load_credentials: 'credentials' key NOT found in session. ---")
        return None

def clear_credentials():
     """Clears credentials from the session."""
     session.pop('credentials', None)
     if config.DEBUG_LOGGING: print("Cleared credentials from session.")

# --- End Token Handling Modification ---

def get_gmail_service():
    """Creates and returns a Gmail API service instance using session storage."""
    if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: Attempting to get service. --- ")
    creds = load_credentials()

    if not creds:
        if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: load_credentials returned None. Returning None. --- ")
        return None 

    if config.DEBUG_LOGGING: print(f"--- DEBUG: get_gmail_service: Credentials loaded. Valid: {creds.valid}, Expired: {creds.expired}, Has Refresh Token: {bool(creds.refresh_token)} ---")

    # Check for scope changes that would cause validation errors during refresh
    from flask import session
    current_auth_scopes = session.get('current_auth_scopes', [])
    
    if hasattr(creds, 'scopes') and current_auth_scopes and set(creds.scopes) != set(current_auth_scopes):
        if config.DEBUG_LOGGING: print(f"--- DEBUG: get_gmail_service: Scope mismatch during service creation: Had {creds.scopes}, session has {current_auth_scopes} ---")
        clear_credentials()
        return None

    if not creds.valid:
        if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: Credentials are not valid. Checking refresh token... ---")
        if creds.expired and creds.refresh_token:
            if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: Credentials expired and refresh token exists. Attempting refresh... ---")
            try:
                creds.refresh(Request())
                if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: Token refreshed successfully. Saving new credentials. ---")
                save_credentials(creds) 
            except Exception as e:
                # If refresh fails due to scope validation, prompt for re-auth
                if "invalid_scope" in str(e).lower() or "scope" in str(e).lower():
                    if config.DEBUG_LOGGING: print(f"--- DEBUG: get_gmail_service: Scope validation error during refresh: {e} ---")
                    clear_credentials()
                    return None
                else:
                    flash(f"Error refreshing credentials: {e}. Please re-authenticate.", "error")
                    if config.DEBUG_LOGGING: print(f"--- DEBUG: get_gmail_service: Token refresh FAILED: {e} ---")
                    clear_credentials() 
                    return None 
        else:
            if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: Credentials invalid/expired OR no refresh token. Clearing credentials and returning None. ---")
            clear_credentials() 
            return None 

    if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: Credentials appear valid. Building Gmail service... ---")
    try:
        # Disable discovery cache for Vercel's ephemeral filesystem
        service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        if config.DEBUG_LOGGING: print("--- DEBUG: get_gmail_service: Gmail service built successfully. Returning service object. ---")
        return service
    except Exception as e:
        flash(f"Error building Gmail service: {e}", "error")
        if config.DEBUG_LOGGING: print(f"--- DEBUG: get_gmail_service: ERROR building Gmail service: {e}. Returning None. ---")
        return None 
        
def has_modify_scope():
    """Check if the current user's credentials include the modify scope."""
    creds = load_credentials()
    if not creds:
        if config.DEBUG_LOGGING: print("--- DEBUG: has_modify_scope: No credentials loaded. Returning False. ---")
        return False
        
    # Check if the modify scope is included in the scopes
    modify_scope = 'https://www.googleapis.com/auth/gmail.modify'
    
    current_scopes = creds.scopes if hasattr(creds, 'scopes') and isinstance(creds.scopes, list) else []
    # Print current scopes for debugging
    if config.DEBUG_LOGGING: print(f"--- DEBUG: has_modify_scope: Checking scopes in loaded creds: {current_scopes} ---")
    
    # Return True if modify_scope is present
    return modify_scope in current_scopes