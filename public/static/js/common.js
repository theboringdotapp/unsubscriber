/**
 * Common utility functions used across multiple pages
 */
document.addEventListener("DOMContentLoaded", function () {
  // Initialize any flash messages
  initFlashMessages();
});

/**
 * Flash message handling
 */
function initFlashMessages() {
  const dismissTime = 6000; // 6 seconds
  const alerts = document.querySelectorAll('.alert[data-auto-dismiss="true"]');

  // Uncomment to enable auto-dismiss
  alerts.forEach((alert) => {
    setTimeout(() => {
      dismissAlert(alert);
    }, dismissTime);
  });
}

/**
 * Dismiss an alert message with animation
 */
function dismissAlert(alertElement) {
  if (!alertElement) return;

  alertElement.classList.add("fade-out");
  setTimeout(() => {
    alertElement.remove();

    // Check if all alerts are gone and remove the container if empty
    const container = document.getElementById("flash-messages");
    if (container && container.children.length === 0) {
      container.remove();
    }
  }, 300);
}

/**
 * Set loading state on a button
 */
function setLoading(buttonId, loadingText = "Processing...") {
  const button = document.getElementById(buttonId);
  if (button) {
    button.disabled = true;
    button.classList.add("is-loading"); // Add class for potential styling
    // Store the original innerHTML for later restoration
    button.dataset.originalContent = button.innerHTML;

    // Create the loading content (spinner class defined in CSS)
    button.innerHTML = `<span class="spinner"></span><span>${loadingText}</span>`;
  }
}

/**
 * Remove loading state from a button
 */
function hideLoading(buttonId) {
  const button = document.getElementById(buttonId);
  if (button && button.classList.contains("is-loading")) {
    // Restore the original content if available
    if (button.dataset.originalContent) {
      button.innerHTML = button.dataset.originalContent;
    }
    button.disabled = false;
    button.classList.remove("is-loading");
  }
}
