# api/config.py
import os
from . import utils # Import utils relatively

if utils.should_log(): print("--- Loading api/config.py ---") # Debug print

# --- Configuration Constants ---

# Google API Scopes - using only readonly for minimum permissions
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Credentials file path (relative to project root)
CREDENTIALS_FILE = 'credentials.json'

# Mock API Flag
MOCK_API = False

# Scan limit
MAX_SCAN_EMAILS = 25
EMAILS_PER_PAGE = 25 # Consistent page size for listing emails

# Colors for sender groups in the UI
SENDER_COLORS = [
    '217 91% 60%', # Blue
    '158 78% 42%', # Green
    '350 89% 60%', # Pink
    '39 95% 55%',  # Orange
    '262 78% 60%', # Purple
    '197 88% 55%', # Cyan
    '22 90% 58%'   # Reddish-Orange
]

# Debug Logging Flag
# DEBUG_LOGGING = os.getenv('FLASK_DEBUG_MODE', 'False').lower() == 'true' # REMOVED - Use utils.should_log() instead

# Gmail API search query terms
# These terms are combined with OR to find emails that might have unsubscribe options
UNSUBSCRIBE_SEARCH_TERMS = [
    'unsubscribe',
    '"manage subscriptions"',
    '"email preferences"', 
    '"click here to unsubscribe"',
    '"opt-out"',
    '"update preferences"',
    '"manage your account"',
    'newsletter'
]

# --- Base URL / Redirect URI (Calculated based on Env Vars) ---
# Calculating these here means they are fixed at import time.
PROD_URL = os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')
DEPLOY_URL = os.environ.get('VERCEL_URL')
VERCEL_ENV = os.environ.get('VERCEL_ENV', 'development') 

_calculated_base_url = None

if PROD_URL and VERCEL_ENV == 'production':
    _calculated_base_url = f"https://{PROD_URL}"
    if utils.should_log(): print(f"--- Config: Using Production URL (HTTPS): {_calculated_base_url} ---")
elif DEPLOY_URL:
    _calculated_base_url = f"http://{DEPLOY_URL}"
    if utils.should_log(): print(f"--- Config: Using Deployment URL (HTTP): {_calculated_base_url} ---")
else:
    # Fallback for local non-vercel execution or if VERCEL_URL isn't set
    _calculated_base_url = 'http://127.0.0.1:5001'
    if utils.should_log(): print(f"--- Config: Using Localhost Fallback URL (HTTP): {_calculated_base_url} ---")

BASE_URL = _calculated_base_url
# Redirect URI includes the auth blueprint prefix
REDIRECT_URI = f'{BASE_URL}/auth/oauth2callback'

if utils.should_log():
    print(f"--- Config: Final BASE_URL: {BASE_URL} ---")
    print(f"--- Config: Final REDIRECT_URI: {REDIRECT_URI} ---")

# Note: FLASK_SECRET_KEY is fetched directly in index.py during app init 