import os
# Set OAuth environment variables to relax token scope validation
# os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'True'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'True'  # For development only

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
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText

# Import Blueprints and utils
from .auth import auth_bp
from .scan import scan_bp
from . import utils # Import utils to access get_gmail_service for the index route
from . import config # Import the config module

# Explicitly tell Flask the template folder is in the root directory
# Calculate the path to the root directory relative to this file (api/index.py)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(project_root, 'templates')
static_dir = os.path.join(project_root, 'public/static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir, static_url_path='/static')

# --- Configuration ---
# Set secret key directly here using environment variable
SECRET_KEY_FROM_ENV = os.environ.get('FLASK_SECRET_KEY')
if not SECRET_KEY_FROM_ENV:
    print("WARNING: FLASK_SECRET_KEY environment variable not set. Using insecure default.")
    SECRET_KEY_FROM_ENV = 'dev-secret-key-replace-this-in-production' 
app.secret_key = SECRET_KEY_FROM_ENV
print(f"--- Flask App Initialized. Using Secret Key: {app.secret_key[:5]}...{app.secret_key[-5:] if len(app.secret_key) > 10 else ''} ---")

# Config values are now primarily in config.py
# Print config loaded from config.py for verification during startup
print(f"--- Using BASE_URL from config: {config.BASE_URL} ---")
print(f"--- Using REDIRECT_URI from config: {config.REDIRECT_URI} ---")
print(f"--- Using MOCK_API from config: {config.MOCK_API} ---")

# Google API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly'] # Read, modify (for archiving), send

# Credentials file path (relative to project root)
CREDENTIALS_FILE = 'credentials.json' 

# Mock API Flag
MOCK_API = False 

# Scan limit
MAX_SCAN_EMAILS = 50 

# --- Vercel Specific Configuration ---
# Prioritize the production URL for OAuth consistency, fall back to deployment URL, then localhost
PROD_URL = os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')
DEPLOY_URL = os.environ.get('VERCEL_URL')
VERCEL_ENV = os.environ.get('VERCEL_ENV', 'development') # Get Vercel environment type

if PROD_URL and VERCEL_ENV == 'production':
    # Use HTTPS for the production domain
    BASE_URL = f"https://{PROD_URL}"
    print(f"--- Using Production URL (HTTPS): {BASE_URL} ---")
elif DEPLOY_URL:
    # Use HTTP for vercel dev (localhost) or preview deployments
    BASE_URL = f"http://{DEPLOY_URL}" 
    print(f"--- Using Deployment URL (HTTP): {BASE_URL} ---")
else:
    # Fallback for truly local execution (e.g. `python api/index.py`)
    BASE_URL = 'http://127.0.0.1:5001' # Default for local development
    print(f"--- Using Localhost Fallback URL (HTTP): {BASE_URL} ---")

# Adjust REDIRECT_URI to include the auth blueprint prefix
REDIRECT_URI = f'{BASE_URL}/auth/oauth2callback' 
print(f"--- Final REDIRECT_URI: {REDIRECT_URI} ---") # Debugging
# --- End Vercel Specific Configuration ---

# --- Register Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(scan_bp)

# --- Main Routes (defined in the main app file) ---
@app.route('/')
def index():
    """Home page: Check credentials and show scan button or login."""
    # Use get_gmail_service from utils
    service = utils.get_gmail_service()
    authenticated = bool(service)
    print(f"Index route: authenticated={authenticated}")
    return render_template('index.html', authenticated=authenticated)

@app.route('/privacy')
def privacy():
    """Privacy Policy page."""
    service = utils.get_gmail_service()
    authenticated = bool(service)
    return render_template('privacy.html', authenticated=authenticated)

# --- Main Execution (for local non-Vercel CLI development) ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gmail Unsubscriber Flask App')
    parser.add_argument('--port', type=int, default=5001, help='Port number.')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode.')
    # Args for local run override (use sparingly)
    parser.add_argument('--mock', action='store_true', help='Use mock Gmail API data.')
    parser.add_argument('--credentials', type=str, default=None, help='Override credentials file path.')
    parser.add_argument('--redirect-host', type=str, default=None, help='Override hostname for OAuth redirect URI.')
    parser.add_argument('--secret-key', type=str, default=None, help='Override Flask secret key.')

    args = parser.parse_args()

    # Apply overrides if provided via command line for direct run
    if args.mock:
        config.MOCK_API = True 
        print("--- CLI Override: Using Mock API --- ")
    if args.credentials:
        config.CREDENTIALS_FILE = args.credentials
        print(f"--- CLI Override: Using Credentials File: {config.CREDENTIALS_FILE} ---")
    if args.secret_key:
        app.secret_key = args.secret_key
        print(f"--- CLI Override: Using Secret Key: {app.secret_key[:5]}... ---")

    # Reconstruct BASE_URL and REDIRECT_URI ONLY if redirect-host is provided
    if args.redirect_host:
        local_base_url = f'http://{args.redirect_host}:{args.port}'
        config.REDIRECT_URI = f'{local_base_url}/auth/oauth2callback' 
        config.BASE_URL = local_base_url 
        print(f"--- CLI Override: Base URL: {config.BASE_URL} ---")
        print(f"--- CLI Override: Redirect URI: {config.REDIRECT_URI} ---")
    
    print("--- Application Start (Local Direct Run) --- ")
    # Print effective settings after potential overrides
    print(f"Mode: {'Mock API' if config.MOCK_API else 'Real API'}")
    print(f"Credentials File: {config.CREDENTIALS_FILE}")
    print(f"Redirect URI: {config.REDIRECT_URI}")
    print(f"Flask Secret Key Used: {app.secret_key[:5]}...{app.secret_key[-5:] if len(app.secret_key) > 10 else ''}")
    print(f"Debug Mode: {args.debug}")
    print(f"Running on: http://0.0.0.0:{args.port} (Accessible via {config.BASE_URL})")
    print("---------------------------------------------")

    app.run(host='0.0.0.0', port=args.port, debug=args.debug) 