# Unsubscriber

> Clean up your inbox in minutes by easily identifying and removing unwanted subscriptions with just a few clicks.

**DISCLAIMER:** This project was built entirely using AI through vibecoding. No code was written by humans.

## Features

- **Intelligent Scanning**: Automatically identifies subscription emails in your Gmail inbox
- **Batch Processing**: Select and unsubscribe from multiple newsletters at once
- **One-Click Unsubscribe**: Simple interface to manage your email subscriptions
- **Sender Grouping**: Emails are organized by sender for easier management
- **Manual Link Access**: Direct access to unsubscribe links when automatic processing isn't possible
- **Secure & Private**: Read-only access by default with optional permission upgrades
- **Free & Open Source**: Free tier supports up to 50 emails per scan

## Setup

### 1. Google Cloud Project & Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Gmail API** for your project
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Choose "Web application" as the application type
6. Add your domain (or `http://localhost:5001`) under "Authorized JavaScript origins"
7. Add your callback URL (or `http://localhost:5001/auth/oauth2callback`) under "Authorized redirect URIs"
8. Create the client ID and download the JSON file as `credentials.json` in the project's root directory
9. **Important**: Add your Google account as a "Test User" in the OAuth consent screen settings

### 2. Python Environment & Dependencies

```bash
# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env.development.local` file in the project root with the following variables:

```
GOOGLE_CREDENTIALS_JSON='content of the credentials.json file'
FLASK_SECRET_KEY=your-secure-random-key
```

- `GOOGLE_CREDENTIALS_JSON`: The entire contents of your credentials.json file as a JSON string
- `FLASK_SECRET_KEY`: A secure random string used by Flask for signing session cookies and protecting against CSRF attacks. Generate a strong key (e.g., using `python -c "import secrets; print(secrets.token_hex(16))"`)

### 4. Vercel CLI (for development)

```bash
# Install Vercel CLI globally
npm install -g vercel
```

## Running the Application

### Local Development with Vercel

The recommended way to run the project locally (handles both frontend and backend):

```bash
# Make sure credentials.json is in the project root
vercel dev --listen 127.0.0.1:5001
```

Open your browser and navigate to `http://localhost:5001`

## Usage

1. **Login**: Click "Login with Google" and authorize the application with read-only access
2. **Scan Inbox**: Click "Scan Inbox Now" to find subscription emails
3. **Select Emails**: Check the emails you want to unsubscribe from
4. **Unsubscribe**: Click "Unsubscribe" to process your selections
5. **Manual Actions**: For links requiring manual interaction, follow the provided instructions
6. **Optional Archiving**: Enable archiving functionality by granting additional permissions when prompted

## Limitations

- Supports HTTP links and mailto: links found in `List-Unsubscribe` headers
- Limited support for links requiring POST requests or complex interactions
- Free tier supports up to 50 emails per scan

## Security & Privacy

- Uses OAuth 2.0 with minimal required permissions (read-only by default)
- Permission-based design with clear explanation of optional extended permissions
- No email content or user data is stored long-term
- All data is processed in-memory and discarded after use
- Transparent permission requests with detailed explanations of what is accessed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

---

Made with ♥ by [theboring.app](https://theboring.app)