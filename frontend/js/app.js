/**
 * Main application logic for Gmail Unsubscriber
 */

// Store references to DOM elements
const elements = {
  loginSection: document.getElementById("login-section"),
  scanSection: document.getElementById("scan-section"),
  resultsSection: document.getElementById("results-section"),
  processingSection: document.getElementById("processing-section"),
  loginBtn: document.getElementById("login-btn"),
  logoutBtn: document.getElementById("logout-btn"),
  scanBtn: document.getElementById("scan-btn"),
  maxResults: document.getElementById("max-results"),
  query: document.getElementById("query"),
  resultsCount: document.getElementById("results-count"),
  emailList: document.getElementById("email-list"),
  selectAllBtn: document.getElementById("select-all-btn"),
  deselectAllBtn: document.getElementById("deselect-all-btn"),
  unsubscribeBtn: document.getElementById("unsubscribe-btn"),
  backBtn: document.getElementById("back-btn"),
  progressBar: document.getElementById("progress"),
  progressText: document.getElementById("progress-text"),
  processingResults: document.getElementById("processing-results"),
  doneBtn: document.getElementById("done-btn"),
};

// Store scanned emails
let scannedEmails = [];

/**
 * Initialize the application
 */
function init() {
  // Set up event listeners
  elements.loginBtn.addEventListener("click", handleLogin);
  elements.logoutBtn.addEventListener("click", handleLogout);
  elements.scanBtn.addEventListener("click", handleScan);
  elements.selectAllBtn.addEventListener("click", handleSelectAll);
  elements.deselectAllBtn.addEventListener("click", handleDeselectAll);
  elements.unsubscribeBtn.addEventListener("click", handleUnsubscribe);
  elements.backBtn.addEventListener("click", handleBack);
  elements.doneBtn.addEventListener("click", handleDone);

  // Update UI based on authentication state
  updateUIForAuth(auth.isAuthenticated());
}

/**
 * Update the UI based on authentication state
 */
function updateUIForAuth(isAuthenticated) {
  if (isAuthenticated) {
    elements.loginSection.classList.add("hidden");
    elements.scanSection.classList.remove("hidden");
    elements.resultsSection.classList.add("hidden");
    elements.processingSection.classList.add("hidden");
  } else {
    elements.loginSection.classList.remove("hidden");
    elements.scanSection.classList.add("hidden");
    elements.resultsSection.classList.add("hidden");
    elements.processingSection.classList.add("hidden");
  }
}

/**
 * Handle login button click
 */
function handleLogin() {
  auth.login();
}

/**
 * Handle logout button click
 */
function handleLogout() {
  auth.logout();
}

/**
 * Handle scan button click
 */
async function handleScan() {
  // Show loading state
  elements.scanBtn.disabled = true;
  elements.scanBtn.innerHTML =
    '<i class="fas fa-spinner fa-spin"></i> Scanning...';

  try {
    // Get parameters
    const maxResults = parseInt(elements.maxResults.value) || 100;
    const query = elements.query.value || "";

    // Make sure token is refreshed
    await auth.refreshTokenIfNeeded();
    const token = auth.getToken();

    if (!token) {
      throw new Error("Not authenticated");
    }

    // Build query string
    const queryParams = new URLSearchParams();
    if (query) queryParams.append("query", query);
    queryParams.append("max_results", maxResults.toString());

    // Make API request
    const response = await fetch(
      `${API_BASE_URL}/scan?${queryParams.toString()}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(token),
      }
    );

    if (!response.ok) {
      throw new Error(`Scan failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    scannedEmails = data.emails || [];

    // Display results
    displayResults(scannedEmails);

    // Show results section
    elements.scanSection.classList.add("hidden");
    elements.resultsSection.classList.remove("hidden");
  } catch (error) {
    console.error("Scan error:", error);
    alert(`Error scanning emails: ${error.message}`);

    // If authentication error, log out
    if (
      error.message.includes("authentication") ||
      error.message.includes("token")
    ) {
      auth.logout();
    }
  } finally {
    // Reset button state
    elements.scanBtn.disabled = false;
    elements.scanBtn.innerHTML = '<i class="fas fa-search"></i> Scan Emails';
  }
}

/**
 * Display scan results
 */
function displayResults(emails) {
  // Update count
  elements.resultsCount.textContent = emails.length;

  // Clear the list
  elements.emailList.innerHTML = "";

  // Add emails to the list
  emails.forEach((email, index) => {
    const emailItem = document.createElement("div");
    emailItem.className = "email-item";

    // Format the from name and date nicely
    const fromParts = email.from.match(/([^<]+)<([^>]+)>/) || [
      null,
      email.from,
      "",
    ];
    const fromName = fromParts[1].trim();
    const fromEmail = fromParts[2].trim();

    const date = new Date(email.date);
    const formattedDate =
      date.toLocaleDateString() +
      " " +
      date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    emailItem.innerHTML = `
            <input type="checkbox" id="email-${index}" class="email-checkbox" data-index="${index}">
            <div class="email-content">
                <div class="email-subject">${escapeHtml(email.subject)}</div>
                <div class="email-from">${escapeHtml(fromName)} ${
      fromEmail ? `(${escapeHtml(fromEmail)})` : ""
    }</div>
                <div class="email-date">${formattedDate}</div>
            </div>
        `;

    elements.emailList.appendChild(emailItem);
  });

  // Add event listeners to checkboxes
  document.querySelectorAll(".email-checkbox").forEach((checkbox) => {
    checkbox.addEventListener("change", updateUnsubscribeButtonState);
  });

  // Initial update of button state
  updateUnsubscribeButtonState();
}

/**
 * Update the state of the unsubscribe button based on selection
 */
function updateUnsubscribeButtonState() {
  const checkedCount = document.querySelectorAll(
    ".email-checkbox:checked"
  ).length;
  elements.unsubscribeBtn.disabled = checkedCount === 0;

  if (checkedCount === 0) {
    elements.unsubscribeBtn.textContent = "Select emails to unsubscribe";
  } else {
    elements.unsubscribeBtn.innerHTML = `<i class="fas fa-unlink"></i> Unsubscribe & Archive ${checkedCount} selected`;
  }
}

/**
 * Handle select all button
 */
function handleSelectAll() {
  document.querySelectorAll(".email-checkbox").forEach((checkbox) => {
    checkbox.checked = true;
  });
  updateUnsubscribeButtonState();
}

/**
 * Handle deselect all button
 */
function handleDeselectAll() {
  document.querySelectorAll(".email-checkbox").forEach((checkbox) => {
    checkbox.checked = false;
  });
  updateUnsubscribeButtonState();
}

/**
 * Handle back button
 */
function handleBack() {
  elements.resultsSection.classList.add("hidden");
  elements.scanSection.classList.remove("hidden");
}

/**
 * Handle unsubscribe button
 */
async function handleUnsubscribe() {
  // Get selected emails
  const selectedIndices = Array.from(
    document.querySelectorAll(".email-checkbox:checked")
  ).map((checkbox) => parseInt(checkbox.dataset.index));

  if (selectedIndices.length === 0) {
    return; // Nothing to do
  }

  const selectedEmails = selectedIndices.map((index) => scannedEmails[index]);

  // Show processing section
  elements.resultsSection.classList.add("hidden");
  elements.processingSection.classList.remove("hidden");
  elements.doneBtn.classList.add("hidden");
  elements.processingResults.innerHTML = "";

  // Initialize progress
  const totalEmails = selectedEmails.length;
  updateProgress(0, totalEmails);

  try {
    // Make sure token is refreshed
    await auth.refreshTokenIfNeeded();
    const token = auth.getToken();

    if (!token) {
      throw new Error("Not authenticated");
    }

    // Process emails
    const results = await processEmails(token, selectedEmails);
    displayProcessingResults(results, selectedEmails);
  } catch (error) {
    console.error("Unsubscribe error:", error);
    alert(`Error processing unsubscribe requests: ${error.message}`);

    // If authentication error, log out
    if (
      error.message.includes("authentication") ||
      error.message.includes("token")
    ) {
      auth.logout();
    }
  } finally {
    elements.doneBtn.classList.remove("hidden");
  }
}

/**
 * Process emails for unsubscribing
 */
async function processEmails(token, emails) {
  const results = [];

  for (let i = 0; i < emails.length; i++) {
    const email = emails[i];

    try {
      // Update progress
      updateProgress(i, emails.length);

      // Make API request for this email
      const response = await fetch(`${API_BASE_URL}/unsubscribe`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          token: token,
          selected_emails: [email],
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      results.push(...data.results);

      // Add a small delay between requests to avoid rate limits
      await new Promise((resolve) => setTimeout(resolve, 200));
    } catch (error) {
      console.error(`Error processing email ${i}:`, error);
      results.push({
        id: email.id,
        unsubscribe_success: false,
        archive_success: false,
        error: error.message,
      });
    }
  }

  // Final progress update
  updateProgress(emails.length, emails.length);

  return results;
}

/**
 * Update progress bar
 */
function updateProgress(current, total) {
  const percentage = (current / total) * 100;
  elements.progressBar.style.width = `${percentage}%`;
  elements.progressText.textContent = `Processing ${current} of ${total} emails...`;
}

/**
 * Display processing results
 */
function displayProcessingResults(results, originalEmails) {
  elements.processingResults.innerHTML = "";

  results.forEach((result) => {
    // Find the original email from the result ID
    const originalEmail =
      originalEmails.find((email) => email.id === result.id) || {};

    const resultItem = document.createElement("div");
    resultItem.className =
      "process-result " +
      (result.unsubscribe_success && result.archive_success
        ? "success"
        : "error");

    let statusIcon, statusText;

    if (result.unsubscribe_success && result.archive_success) {
      statusIcon = '<i class="fas fa-check-circle result-icon"></i>';
      statusText = "Successfully unsubscribed and archived";
    } else if (result.unsubscribe_success) {
      statusIcon = '<i class="fas fa-exclamation-circle result-icon"></i>';
      statusText = "Unsubscribed but failed to archive";
    } else if (result.archive_success) {
      statusIcon = '<i class="fas fa-exclamation-circle result-icon"></i>';
      statusText = "Archived but failed to unsubscribe";
    } else {
      statusIcon = '<i class="fas fa-times-circle result-icon"></i>';
      statusText = "Failed to unsubscribe and archive";
    }

    resultItem.innerHTML = `
            ${statusIcon}
            <div>
                <div class="email-subject">${escapeHtml(
                  originalEmail.subject || "Unknown Email"
                )}</div>
                <div>${statusText}</div>
                ${
                  result.error
                    ? `<div class="error-details">Error: ${escapeHtml(
                        result.error
                      )}</div>`
                    : ""
                }
            </div>
        `;

    elements.processingResults.appendChild(resultItem);
  });
}

/**
 * Handle the done button click
 */
function handleDone() {
  // Return to scan section
  elements.processingSection.classList.add("hidden");
  elements.scanSection.classList.remove("hidden");
}

/**
 * Helper function to escape HTML
 */
function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Initialize the app when DOM is ready
document.addEventListener("DOMContentLoaded", init);
