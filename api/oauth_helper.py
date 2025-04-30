"""Helper module for OAuth flow to avoid scope validation errors.

This is a modified version of the google_auth_oauthlib fetch_token method
that doesn't validate if the scopes have changed during the OAuth flow.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

# Override the fetch_token method to skip scope validation
class NoScopeValidationFlow(InstalledAppFlow):
    """OAuth 2.0 Authorization Flow that doesn't validate scope changes."""
    
    def fetch_token(self, **kwargs):
        """Fetch an access token.

        This is a modified version that skips scope validation.
        
        Args:
            kwargs: Additional arguments passed to requests.Session.fetch_token.

        Returns:
            The obtained tokens.
        """
        # Get the token via the OAuth session
        return self.oauth2session.fetch_token(
            self.client_config['token_uri'],
            client_secret=self.client_config['client_secret'],
            **kwargs)