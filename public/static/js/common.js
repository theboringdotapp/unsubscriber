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
function setLoading(buttonId, loadingText) {
  const button = document.getElementById(buttonId);
  if (button) {
    button.disabled = true;
    // Store original text
    button.dataset.originalText = button.innerHTML;
    // Add spinner and loading text
    button.innerHTML = `<span class="spinner mr-2"></span> ${loadingText}`;
  }
}

/**
 * Remove loading state from a button
 */
function resetButton(buttonId) {
  const button = document.getElementById(buttonId);
  if (button && button.dataset.originalText) {
    button.disabled = false;
    button.innerHTML = button.dataset.originalText;
  }
}

// Function to show alerts
function showAlert(type, message) {
  const alertContainer = document.getElementById("alert-container");
  if (!alertContainer) {
    console.error("Alert container not found");
    return;
  }

  // Create alert element
  const alertDiv = document.createElement("div");
  alertDiv.className = `alert alert-${type}`;
  alertDiv.setAttribute("role", "alert");

  let iconSvg = "";
  // Choose icon based on type
  switch (type) {
    case "success":
      iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`;
      break;
    case "destructive": // Assuming 'error' maps to 'destructive'
      iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>`;
      break;
    case "warning":
      iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>`;
      break;
    case "info":
      iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" /></svg>`;
      break;
  }

  alertDiv.innerHTML = `
    <div class="alert-content">
      <span class="alert-icon">${iconSvg}</span>
      <span>${message}</span>
    </div>
    <button class="alert-close" onclick="this.parentElement.remove()">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
    </button>
  `;

  // Prepend the alert to the container
  alertContainer.prepend(alertDiv);

  // Optional: Auto-dismiss after some time (e.g., 5 seconds)
  setTimeout(() => {
    alertDiv.classList.add("fade-out");
    // Remove the element after the fade-out transition completes
    alertDiv.addEventListener("transitionend", () => alertDiv.remove());
  }, 5000);
}

// --- CASA Disclosure Modal --- //
function openDisclosureModal() {
  const modal = document.getElementById("casa-disclosure-modal");
  if (modal) {
    modal.classList.remove("modal-hidden");
    modal.classList.add("visible");
    // Add ARIA attributes for accessibility
    modal.setAttribute("aria-hidden", "false");
    modal.setAttribute("tabindex", "-1"); // Allow focus
    modal.focus(); // Focus the modal itself
  }
}

function closeDisclosureModal() {
  const modal = document.getElementById("casa-disclosure-modal");
  if (modal) {
    modal.classList.add("modal-hidden");
    modal.classList.remove("visible");
    // Add ARIA attributes for accessibility
    modal.setAttribute("aria-hidden", "true");
    modal.removeAttribute("tabindex");
    // Optionally return focus to the trigger button
    const triggerButton = document.getElementById("scan-inbox-button");
    if (triggerButton) {
      triggerButton.focus();
    }
  }
}

// Add event listener for ESC key to close modal
document.addEventListener("keydown", function (event) {
  const modal = document.getElementById("casa-disclosure-modal");
  if (event.key === "Escape" && modal && modal.classList.contains("visible")) {
    closeDisclosureModal();
  }
});

// Close modal if clicking outside the modal content
document.addEventListener("click", function (event) {
  const modal = document.getElementById("casa-disclosure-modal");
  const modalContent = modal ? modal.querySelector(".card") : null;

  if (modal && modal.classList.contains("visible") && modalContent) {
    // Check if the click target is the modal overlay itself (not the content)
    if (!modalContent.contains(event.target) && event.target === modal) {
      closeDisclosureModal();
    }
  }
});
