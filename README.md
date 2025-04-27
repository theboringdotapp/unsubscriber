# Gmail Bulk Unsubscriber MVP

A simple Flask application to scan your Gmail account, identify emails with unsubscribe links (primarily using the `List-Unsubscribe` header), and allow you to bulk unsubscribe and archive them.

## Features

*   Authenticates with your Google Account using OAuth 2.0.
*   Scans recent emails (or those matching a basic query) for `List-Unsubscribe` headers.
*   Displays a list of emails with potential unsubscribe links.
*   Allows selection of emails to process.
*   Attempts to visit the unsubscribe link (via HTTP GET).
*   Archives the selected emails in Gmail.

## Setup

1.  **Google Cloud Project & Credentials:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project (or use an existing one).
    *   Enable the **Gmail API** for your project.
    *   Go to "Credentials" -> "Create Credentials" -> "OAuth client ID".
    *   Choose "Web application" as the application type.
    *   Add `http://localhost:5000` under "Authorized JavaScript origins".
    *   Add `http://localhost:5000/oauth2callback` under "Authorized redirect URIs".
    *   Create the client ID. Download the JSON file and save it as `credentials.json` in the project's root directory.
    *   **IMPORTANT:** You might need to add your Google account as a "Test User" in the OAuth consent screen settings while the app is in the "Testing" publishing status, otherwise, Google might block the login.

2.  **Python Environment & Dependencies:**
    *   It's recommended to use a virtual environment:
        ```bash
        python3 -m venv venv
        source venv/bin/activate  # On Windows use `venv\Scripts\activate`
        ```
    *   Install the required packages:
        ```bash
        pip install -r requirements.txt
        ```

## Running the Application

1.  Make sure `credentials.json` is in the same directory as `app.py`.
2.  Run the Flask development server:
    ```bash
    python app.py
    ```
3.  Open your web browser and navigate to `http://localhost:5000`.
4.  Click "Login with Google" and follow the authentication flow. You will likely see a warning screen from Google because the app isn't verified; you'll need to proceed through the "advanced" options to allow access.
5.  Once authenticated, click "Scan Emails for Unsubscribe Links".
6.  Select the emails you want to unsubscribe from and click "Unsubscribe & Archive Selected".

## Limitations & Future Improvements (MVP)

*   **Unsubscribe Method:** Only handles HTTP GET links found in `List-Unsubscribe` headers. Does not handle `mailto:` links or complex unsubscribe forms requiring POST requests or JavaScript.
*   **Link Visiting:** Simply makes a GET request. Success isn't guaranteed, and some links might require browser interaction.
*   **Email Parsing:** Does not currently parse the email body for unsubscribe links, only the headers.
*   **Error Handling:** Basic error handling. Could be more robust.
*   **Scalability:** Scans a limited number of recent emails. Not suitable for very large mailboxes without adjustments.
*   **Security:** Stores OAuth tokens (`token.pickle`) locally. Suitable for personal use but not for a shared environment. `credentials.json` should also be kept secure.
*   **UI:** Very basic user interface. 