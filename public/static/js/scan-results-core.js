/**
 * Core functionality for the scan results page
 * Handles storage management and UI state
 */

// Constants
const storageKey = "selectedEmailIds";
const detailsStorageKey = "emailDetails";
const MAX_EMAILS = 25; // Maximum number of emails that can be selected/processed at once

// --- Storage Helper Functions ---
function getSelectedEmailsFromStorage() {
  const stored = sessionStorage.getItem(storageKey);
  try {
    return stored ? JSON.parse(stored) : [];
  } catch (e) {
    console.error("Error parsing selectedEmails from sessionStorage:", e);
    return [];
  }
}

function saveSelectedEmailsToStorage(emailIdsArray) {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(emailIdsArray));
  } catch (e) {
    console.error("Error saving selectedEmails to sessionStorage:", e);
  }
}

function getEmailDetailsFromStorage() {
  const stored = sessionStorage.getItem(detailsStorageKey);
  try {
    return stored ? JSON.parse(stored) : {};
  } catch (e) {
    console.error("Error parsing emailDetails from sessionStorage:", e);
    return {};
  }
}

function saveEmailDetailsToStorage(emailDetailsObj) {
  try {
    sessionStorage.setItem(detailsStorageKey, JSON.stringify(emailDetailsObj));
  } catch (e) {
    console.error("Error saving emailDetails to sessionStorage:", e);
  }
}

// Update storage based on checkbox state
function updateStorageForItem(emailId, isSelected) {
  let selectedIds = getSelectedEmailsFromStorage();
  if (isSelected) {
    if (!selectedIds.includes(emailId)) {
      selectedIds.push(emailId);

      // Also store detailed information for this email if available
      const emailRow = document.getElementById(`email-${emailId}`);
      if (emailRow) {
        const checkbox = emailRow.querySelector(".email-checkbox");
        if (checkbox) {
          const sender = checkbox.getAttribute("data-sender");

          // Get the sender group element to find unsubscribe link
          let unsubscribeLink = null;
          if (sender) {
            const senderId = sender
              .replace(/\s+/g, "-")
              .replace(/[<>]/g, "")
              .replace(/@/g, "-")
              .replace(/\./g, "-")
              .replace(/['"`()]/g, ""); // Remove special characters

            const senderGroup = document.getElementById(
              `sender-group-${senderId}`
            );
            if (senderGroup) {
              const headerLinks =
                senderGroup.querySelectorAll(".sender-header a");
              if (headerLinks.length > 0) {
                unsubscribeLink = headerLinks[0].getAttribute("href") || null;
              }
            }
          }

          // Store the email details
          const emailDetails = getEmailDetailsFromStorage();
          emailDetails[emailId] = {
            id: emailId,
            sender: sender || null,
            link: unsubscribeLink,
            type: unsubscribeLink
              ? unsubscribeLink.startsWith("mailto:")
                ? "mailto"
                : "http"
              : null,
          };
          saveEmailDetailsToStorage(emailDetails);
        }
      }
    }
  } else {
    selectedIds = selectedIds.filter((id) => id !== emailId);

    // Remove this email from the details storage as well
    const emailDetails = getEmailDetailsFromStorage();
    if (emailDetails[emailId]) {
      delete emailDetails[emailId];
      saveEmailDetailsToStorage(emailDetails);
    }
  }
  saveSelectedEmailsToStorage(selectedIds);
}

function storeProcessedSenders(senders) {
  const processedKey = "processedSenders";
  let existingSenders = [];
  try {
    const stored = sessionStorage.getItem(processedKey);
    existingSenders = stored ? JSON.parse(stored) : [];
  } catch (e) {
    console.error("Error parsing processedSenders from sessionStorage:", e);
    existingSenders = [];
  }

  // Add new senders without duplication
  const updatedSenders = [...new Set([...existingSenders, ...senders])];

  try {
    sessionStorage.setItem(processedKey, JSON.stringify(updatedSenders));
    console.log("Stored processed senders:", updatedSenders);
  } catch (e) {
    console.error("Error saving processedSenders to sessionStorage:", e);
  }
}

function getProcessedSenders() {
  const processedKey = "processedSenders";
  try {
    const stored = sessionStorage.getItem(processedKey);
    return stored ? JSON.parse(stored) : [];
  } catch (e) {
    console.error("Error retrieving processedSenders:", e);
    return [];
  }
}

// --- Action Bar Update ---
function updateActionBar() {
  const selectedEmailIds = getSelectedEmailsFromStorage();
  const count = selectedEmailIds.length;

  // Get action bar elements
  const actionBar = document.getElementById("fixed-action-bar");
  const actionText = document.getElementById("action-count");
  const progressBar = document.getElementById("email-limit-progress");
  const emailCountCurrent = document.getElementById("email-count-current");
  const emailCountMax = document.getElementById("email-count-max");

  if (!actionBar || !actionText) return;

  // Update the count text
  actionText.textContent =
    count === 1 ? "1 email selected" : `${count} emails selected`;

  // Update progress bar
  if (progressBar && emailCountCurrent && emailCountMax) {
    const progressPercent = (count / MAX_EMAILS) * 100;
    progressBar.style.width = `${progressPercent}%`;
    emailCountCurrent.textContent = count;
    emailCountMax.textContent = MAX_EMAILS;

    // Change progress bar color when approaching limit
    if (progressPercent >= 90) {
      progressBar.classList.remove("bg-brand");
      progressBar.style.backgroundColor = "rgb(245, 158, 11)"; // Amber-500 color
    } else {
      progressBar.style.backgroundColor = ""; // Reset to default
      progressBar.classList.add("bg-brand");
    }
  }

  // Toggle visibility based on selection
  if (count > 0) {
    actionBar.classList.remove("hidden");
  } else {
    actionBar.classList.add("hidden");
  }
}

// --- Modal Management ---
function showModal(content) {
  const modal = document.getElementById("result-modal");
  const modalContent = document.getElementById("modal-content");
  if (!modal || !modalContent) return;
  modalContent.innerHTML = content;
  modal.classList.remove("hidden");
  modal.classList.add("visible");
}

function closeModal() {
  const modal = document.getElementById("result-modal");
  if (!modal) return;
  modal.classList.remove("visible");

  setTimeout(() => {
    modal.classList.add("hidden");
    document.getElementById("modal-content").innerHTML = "";
  }, 300);
  updateActionBar();
}

function showPermissionModal() {
  const modal = document.getElementById("permission-modal");
  if (modal) {
    modal.classList.remove("hidden");
    modal.classList.add("visible");
  }
}

function closePermissionModal() {
  const modal = document.getElementById("permission-modal");
  if (modal) {
    modal.classList.remove("visible");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}
