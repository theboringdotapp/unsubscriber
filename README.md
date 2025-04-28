# Gmail Bulk Unsubscriber - Serverless Edition

A serverless application to scan your Gmail account, identify emails with unsubscribe links, and allow you to bulk unsubscribe and archive them.

## Architecture

This application uses a provider-agnostic serverless architecture:

- **Frontend**: Static HTML/JavaScript that handles UI and state management
- **API functions**: Stateless serverless functions for authentication, scanning emails, and unsubscribing
- **State management**: Tokens and state handled in browser storage

## Project Structure

```
/
├── api/                 # Serverless functions (Python)
│   ├── auth.py          # Authentication endpoints
│   ├── scan.py          # Email scanning functionality
│   └── unsubscribe.py   # Unsubscribe functionality
├── frontend/            # Client-side application
│   ├── index.html       # Main page
│   ├── js/              # JavaScript files
│   └── css/             # Stylesheets
└── README.md            # This documentation
```

## Features

* Authenticates with your Google Account using OAuth 2.0.
* Scans recent emails for `List-Unsubscribe` headers.
* Displays a list of emails with potential unsubscribe links.
* Allows selection of emails to process.
* Attempts to visit the unsubscribe link (via HTTP GET).
* Archives the selected emails in Gmail.

## Setup

1. **Google Cloud Project & Credentials:**
   * Go to the [Google Cloud Console](https://console.cloud.google.com/).
   * Create a new project (or use an existing one).
   * Enable the **Gmail API** for your project.
   * Go to "Credentials" -> "Create Credentials" -> "OAuth client ID".
   * Choose "Web application" as the application type.
   * Add your frontend URL (or `http://localhost:5000` for development) under "Authorized JavaScript origins".
   * Add your redirect URL (or `http://localhost:5000/api/callback` for development) under "Authorized redirect URIs".
   * Create the client ID. Download the JSON file and save it as `credentials.json`.
   * You might need to add your Google account as a "Test User" in the OAuth consent screen settings.

2. **Provider-specific deployment:**

   **Local Development:**
   ```bash
   # Install dependencies
   pip install -r api/requirements.txt
   
   # Run API locally (using a tool like functions-framework)
   functions-framework --target=auth_handler --source=api/auth.py --port=8080
   
   # Serve frontend (in another terminal)
   cd frontend && python -m http.server 5000
   ```

   **Vercel:**
   - Deploy directly from the repository
   - All `/api` functions are automatically deployed as serverless functions
   - Frontend is automatically built and deployed

   **Netlify:**
   - Add a `netlify.toml` file to configure functions directory
   - Functions should be in the `netlify/functions` directory (can be symlinks)

   **Firebase:**
   - Use Firebase Hosting for the frontend
   - Use Firebase Functions for the API (requires a `functions/` directory)

   **AWS:**
   - Use S3 + CloudFront for frontend
   - Use API Gateway + Lambda for the API functions

## Security Considerations

- OAuth tokens are stored in browser storage
- Consider implementing CSRF protection
- Use environment variables for sensitive information 