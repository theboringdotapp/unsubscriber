/**
 * Authentication handler for Gmail unsubscriber
 */

// API URLs - change these based on deployment environment
const API_BASE_URL =
  window.location.hostname === "localhost"
    ? "http://localhost:8080/api"
    : "/api"; // For production, this will be relative to the deployed domain

// Token storage key in localStorage
const TOKEN_STORAGE_KEY = "gmail_unsubscriber_token";

/**
 * Auth class to handle Google authentication
 */
class Auth {
  constructor() {
    this.token = null;
    this.loadTokenFromStorage();
    this.checkUrlFragmentForToken();
  }

  /**
   * Load token from localStorage if it exists
   */
  loadTokenFromStorage() {
    const tokenStr = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (tokenStr) {
      try {
        this.token = JSON.parse(tokenStr);
        console.log("Loaded token from storage");
      } catch (e) {
        console.error("Failed to parse token from storage", e);
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    }
  }

  /**
   * Check URL fragment for token after OAuth redirect
   */
  checkUrlFragmentForToken() {
    if (window.location.hash.includes("#token=")) {
      // Extract token from URL fragment
      const tokenParam = window.location.hash.split("#token=")[1];
      try {
        this.token = JSON.parse(decodeURIComponent(tokenParam));
        console.log("Received token from redirect");

        // Save token to storage
        this.saveTokenToStorage();

        // Clean up the URL
        window.history.replaceState(
          {},
          document.title,
          window.location.pathname
        );

        // Update UI based on authentication state
        if (typeof updateUIForAuth === "function") {
          updateUIForAuth(true);
        }
      } catch (e) {
        console.error("Failed to parse token from URL fragment", e);
      }
    } else if (window.location.hash.includes("#error=")) {
      // Handle authentication error
      const error = window.location.hash.split("#error=")[1];
      console.error("Authentication error:", decodeURIComponent(error));
      alert("Authentication error: " + decodeURIComponent(error));

      // Clean up the URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  /**
   * Save token to localStorage
   */
  saveTokenToStorage() {
    if (this.token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(this.token));
    }
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!this.token;
  }

  /**
   * Start the login process
   */
  login() {
    window.location.href = `${API_BASE_URL}/auth/login`;
  }

  /**
   * Log the user out
   */
  logout() {
    this.token = null;
    localStorage.removeItem(TOKEN_STORAGE_KEY);

    // Update UI based on authentication state
    if (typeof updateUIForAuth === "function") {
      updateUIForAuth(false);
    }
  }

  /**
   * Refresh the token if needed
   */
  async refreshTokenIfNeeded() {
    // This is a simplistic check - in a real app, you'd want to check
    // token expiration more carefully
    if (!this.token) return false;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(this.token),
      });

      if (!response.ok) {
        throw new Error("Token refresh failed");
      }

      const refreshedToken = await response.json();
      this.token = refreshedToken;
      this.saveTokenToStorage();
      return true;
    } catch (e) {
      console.error("Failed to refresh token", e);
      // If refresh fails, user needs to re-authenticate
      this.logout();
      return false;
    }
  }

  /**
   * Get the current token
   */
  getToken() {
    return this.token;
  }
}

// Create a global auth instance
const auth = new Auth();
