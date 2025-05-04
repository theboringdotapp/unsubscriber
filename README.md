# Unsubscriber

A simple Flask web application to help users easily find and unsubscribe from mailing lists in their Gmail account.

## Features

*   **Google OAuth:** Securely authenticate using your Google account.
*   **Email Scanning:** Scans recent emails for common unsubscribe headers and links.
*   **Subscription Grouping:** Groups emails by sender for easier identification.
*   **One-Click Unsubscribe:** Attempts to automatically unsubscribe using `List-Unsubscribe` headers (both `mailto:` and HTTP links).
*   **Batch Archiving (Optional):** Allows users to archive processed emails after unsubscribing (requires additional permissions).
*   **Privacy Focused:** Does not store email content long-term. Processes data transiently.
*   **Open Source:** Code available for review and contribution.
*   **Theme Toggle:** Light and Dark mode support.

## Project Structure

```
/gmail-bulk-unsub
├── api/                  # Flask API backend (Serverless Function on Vercel)
│   ├── __init__.py
│   ├── index.py          # Main Flask app setup, /dashboard route
│   ├── auth.py           # Google OAuth authentication logic
│   ├── scan.py           # Gmail scanning and unsubscribe logic
│   ├── utils.py          # Helper functions (Gmail service, credentials)
│   └── config.py         # Configuration variables
├── public/               # Static assets served directly by Vercel
│   ├── index.html        # Static landing page for unauthenticated users
│   ├── privacy.html      # Static privacy policy page
│   └── static/           # CSS, JS, Images
│       ├── css/
│       ├── js/
│       └── img/
├── templates/            # Jinja2 templates used by the Flask app (authenticated views)
│   ├── base.html         # Base template with nav/footer
│   ├── index.html        # Authenticated dashboard view
│   ├── scan_results.html # Results page after scanning
│   └── partials/         # Template partials (e.g., modal content)
├── credentials.json      # Google OAuth Client Secrets (Add to .gitignore!)
├── requirements.txt      # Python dependencies
├── vercel.json           # Vercel deployment configuration (routing, builds)
├── .gitignore
└── README.md
```

## Setup and Running Locally

1.  **Prerequisites:**
    *   Python 3.8+
    *   `pip`
    *   Google Cloud Project with OAuth 2.0 Client ID credentials (see below).

2.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/gmail-bulk-unsub.git
    cd gmail-bulk-unsub
    ```

3.  **Create Google OAuth Credentials:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the **Gmail API** under "APIs & Services" > "Library".
    *   Go to "APIs & Services" > "Credentials".
    *   Click "+ CREATE CREDENTIALS" > "OAuth client ID".
    *   Select "Web application" as the application type.
    *   Give it a name (e.g., "Gmail Unsubscriber Local").
    *   Under "Authorized JavaScript origins", add `http://localhost:5001` and `http://127.0.0.1:5001`.
    *   Under "Authorized redirect URIs", add `http://localhost:5001/auth/oauth2callback` and `http://127.0.0.1:5001/auth/oauth2callback`.
    *   Click "Create".
    *   Download the JSON credentials file and save it as `credentials.json` in the project root directory. **IMPORTANT:** Add `credentials.json` to your `.gitignore` file to avoid committing secrets.

4.  **Set up Python Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

5.  **Set Environment Variables (Optional but Recommended):**
    *   Create a `.env` file in the root directory (add `.env` to `.gitignore`).
    *   Add a strong secret key:
        ```
        FLASK_SECRET_KEY='your_strong_random_secret_key'
        ```
        You can generate one using `python -c 'import secrets; print(secrets.token_hex())'`.
    *   If you prefer not to use `.env`, you can set the variable directly in your shell:
        ```bash
        export FLASK_SECRET_KEY='your_strong_random_secret_key'
        ```
    *   To enable debug logging locally:
        ```bash
        export FLASK_DEBUG_MODE=True
        ```

6.  **Run the Flask App:**
    ```bash
    # Ensure FLASK_SECRET_KEY is set (either via .env loaded or exported)
    python api/index.py --port 5001 --debug
    ```
    *   The `--debug` flag enables Flask's debug mode.
    *   The app will be accessible at `http://127.0.0.1:5001` or `http://localhost:5001`.

## Deployment (Vercel)

This app is structured for easy deployment on [Vercel](https://vercel.com/).

1.  **Push to Git:** Ensure your code is pushed to a Git repository (GitHub, GitLab, Bitbucket).
2.  **Import Project:** Import your Git repository into Vercel.
3.  **Configure Project Settings:**
    *   **Build Command:** Leave empty or use `pip install -r requirements.txt` if needed (Vercel usually detects `requirements.txt` automatically).
    *   **Output Directory:** Leave as default.
    *   **Install Command:** Leave as default (`pip install --upgrade pip && pip install -r requirements.txt`).
    *   **Development Command:** `python api/index.py --port $PORT` (Useful for `vercel dev`).
4.  **Environment Variables:** Set the following environment variables in your Vercel project settings:
    *   `FLASK_SECRET_KEY`: Your strong secret key.
    *   `GOOGLE_CREDENTIALS_JSON`: Paste the *entire content* of your `credentials.json` file here. **Important:** When creating/updating credentials in Google Cloud for Vercel:
        *   Add your Vercel production URL (e.g., `https://your-app-name.vercel.app`) to "Authorized JavaScript origins".
        *   Add `https://your-app-name.vercel.app/auth/oauth2callback` to "Authorized redirect URIs".
    *   `FLASK_DEBUG_MODE` (Optional): Set to `False` or remove for production.
5.  **Deploy:** Vercel will build and deploy your application.

**Vercel Structure Notes:**

*   The `vercel.json` file configures routing.
*   Static files (`/public/index.html`, `/public/privacy.html`, `/public/static/*`) are served directly by Vercel's CDN.
*   API routes (`/dashboard`, `/auth/*`, `/scan/*`) are handled by the Flask app running as a Serverless Function (`api/index.py`).
*   This minimizes function invocations for unauthenticated users, improving performance and reducing costs.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an Issue.

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

## Vibe Coding Analytics

This project was developed 100% using Vibe Coding (AI-assisted development) with almost no human-written code.

### AI Models Used
- Claude-3.7-sonnet
- Gemini 2.5 Pro

### Tools Used
- [Cursor.sh](https://cursor.sh) - AI-powered code editor
- [Claude Code CLI](https://claude.ai/code) - Command line coding assistant

### Development Costs
- $20.00 - Cursor subscription (used all 500 fast requests)
- $13.81 - Extra Cursor credits
- $21.42 - Claude Code credits (used for complex tasks)
- **Total: $55.23**

### Time Metrics
<!-- START_GIT_TIME_STATS -->
*(Stats will be automatically inserted here by a GitHub Action)*
<!-- END_GIT_TIME_STATS -->

*Time is calculated based on the commit history, so not 100% accurate.