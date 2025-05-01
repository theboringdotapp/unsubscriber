import os
# Set OAuth environment variables to relax token scope validation
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'True'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'True'  # For development only
os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = 'True'  # Ignore scope changes during auth flow

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
from . import utils # Import utils to access get_gmail_service
from . import config # Import the config module

# Explicitly tell Flask the template folder is in the root directory
# Calculate the path to the root directory relative to this file (api/index.py)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(project_root, 'templates')
static_dir = os.path.join(project_root, 'public/static')

# NOTE: static_folder is handled by vercel.json now, but keep for local dev?
# For Vercel, static files are served directly based on vercel.json, not via Flask.
# Setting static_folder here might be useful for local `flask run` but potentially confusing.
# Let's remove it to rely solely on Vercel's handling for static files.
app = Flask(__name__, template_folder=template_dir)

# --- Configuration ---
# Set secret key directly here using environment variable
SECRET_KEY_FROM_ENV = os.environ.get('FLASK_SECRET_KEY')
if not SECRET_KEY_FROM_ENV:
    print("WARNING: FLASK_SECRET_KEY environment variable not set. Using insecure default.")
    SECRET_KEY_FROM_ENV = 'dev-secret-key-replace-this-in-production' 
app.secret_key = SECRET_KEY_FROM_ENV
print(f"--- Flask App Initialized. Using Secret Key: {app.secret_key[:5]}...{app.secret_key[-5:] if len(app.secret_key) > 10 else ''} ---")

# --- Update Config based on Environment Variable ---
# Read the debug logging flag *after* app init, ensuring env vars are loaded
# config.DEBUG_LOGGING = os.getenv('FLASK_DEBUG_MODE', 'False').lower() == 'true' # Use utils.should_log()
if utils.should_log():
    print("--- FLASK_DEBUG_MODE is TRUE --- Verbosely logging startup config...")
# --- End Update Config ---

# Config values are now primarily in config.py
# Print config loaded from config.py for verification during startup
if utils.should_log():
    print(f"--- Using BASE_URL from config: {config.BASE_URL} ---")
    print(f"--- Using REDIRECT_URI from config: {config.REDIRECT_URI} ---")
    print(f"--- Using MOCK_API from config: {config.MOCK_API} ---")

# Google API Scopes are defined in config.py
# Credentials file path is defined in config.py

# --- Vercel Specific Configuration (Now mainly in config.py) ---
if utils.should_log(): print(f"--- Final REDIRECT_URI from config: {config.REDIRECT_URI} ---")
# --- End Vercel Specific Configuration ---

# --- Register Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(scan_bp)

# --- Main Routes (defined in the main app file) ---

# Removed the '/' and '/privacy' routes as they are now served statically by Vercel

@app.route('/dashboard')
def dashboard():
    """Dashboard page shown after successful login."""
    service = utils.get_gmail_service()
    if not service:
        flash("Please log in to view the dashboard.", "warning")
        return redirect(url_for('auth.login')) # Redirect to login if not authenticated

    # Render the template previously used for the authenticated part of index
    # This template now assumes user is authenticated
    if utils.should_log(): print("Rendering dashboard (templates/index.html) for authenticated user.")
    return render_template('index.html', authenticated=True)


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
        if utils.should_log(): print("--- CLI Override: Using Mock API --- ")
    if args.credentials:
        config.CREDENTIALS_FILE = args.credentials
        if utils.should_log(): print(f"--- CLI Override: Using Credentials File: {config.CREDENTIALS_FILE} ---")
    if args.secret_key:
        app.secret_key = args.secret_key
        if utils.should_log(): print(f"--- CLI Override: Using Secret Key: {app.secret_key[:5]}... ---")

    # Reconstruct BASE_URL and REDIRECT_URI ONLY if redirect-host is provided
    # This affects config values if running locally with override
    if args.redirect_host:
        local_base_url = f'http://{args.redirect_host}:{args.port}'
        config.BASE_URL = local_base_url # Update config
        config.REDIRECT_URI = f'{local_base_url}/auth/oauth2callback' # Update config
        if utils.should_log():
            print(f"--- CLI Override: Base URL: {config.BASE_URL} ---")
            print(f"--- CLI Override: Redirect URI: {config.REDIRECT_URI} ---")

    if utils.should_log(): print("--- Application Start (Local Direct Run) --- ")
    # Print effective settings after potential overrides
    if utils.should_log():
        print(f"Mode: {'Mock API' if config.MOCK_API else 'Real API'}")
        print(f"Credentials File: {config.CREDENTIALS_FILE}")
        print(f"Redirect URI: {config.REDIRECT_URI}")
        print(f"Flask Secret Key Used: {app.secret_key[:5]}...{app.secret_key[-5:] if len(app.secret_key) > 10 else ''}")
        print(f"Debug Mode: {args.debug}")
        print(f"Running on: http://0.0.0.0:{args.port} (Accessible via {config.BASE_URL or 'http://127.0.0.1:' + str(args.port)}) ")
        print("---------------------------------------------")

    # For local development, tell Flask where static files are if not using Vercel
    # Check if VERCEL env var is NOT set to determine if truly local
    if not os.environ.get('VERCEL'):
        print("--- Local Run Detected (no VERCEL env var): Configuring static folder for Flask --- ")
        app.static_folder = static_dir
        app.static_url_path = '/static'

    app.run(host='0.0.0.0', port=args.port, debug=args.debug) 
