/**
 * Handles the main unsubscribe process for the scan results page
 */

// Global variables for tracking unsubscribe process
let unsubscribeUrl = ""; // Will be set from the template
let archiveUrl = ""; // Will be set from the template

/**
 * Set URL endpoints for API calls
 * Called from the template
 */
function setEndpoints(unsubUrl, archUrl) {
  unsubscribeUrl = unsubUrl;
  archiveUrl = archUrl;
  console.log("Endpoints set:", { unsubscribeUrl, archiveUrl });
}

/**
 * Saves email details to session storage
 */
function saveEmailDetailsToStorage(details) {
  try {
    sessionStorage.setItem("emailDetails", JSON.stringify(details));
  } catch (e) {
    console.error("Failed to save email details to session storage:", e);
  }
}

/**
 * Gets email details from session storage
 */
function getEmailDetailsFromStorage() {
  try {
    const details = sessionStorage.getItem("emailDetails");
    return details ? JSON.parse(details) : {};
  } catch (e) {
    console.error("Failed to get email details from session storage:", e);
    return {};
  }
}

/**
 * Initialize data storage for the current page's emails
 * Called on page load
 */
function initializeEmailDataStore() {
  const emailRows = document.querySelectorAll(".email-row");
  const storedDetails = getEmailDetailsFromStorage(); // Get potentially existing data

  emailRows.forEach((row) => {
    const emailId = row.id.replace("email-", "");
    const checkbox = row.querySelector(".email-checkbox");

    if (!checkbox) {
      return; // Skip if no checkbox
    }

    const sender = checkbox.getAttribute("data-sender");
    if (!sender) return;

    // Extract all link data from attributes
    const headerLink = checkbox.getAttribute("data-header-link");
    const mailtoLink = checkbox.getAttribute("data-mailto-link");
    const bodyLink = checkbox.getAttribute("data-body-link");
    const primaryLink = checkbox.getAttribute("data-primary-link"); // Keep this if needed

    // Store or update email details with all links
    storedDetails[emailId] = {
      id: emailId,
      sender: sender,
      header_link: headerLink,
      mailto_link: mailtoLink,
      body_link: bodyLink,
    };
  });

  // Save the updated details to storage
  saveEmailDetailsToStorage(storedDetails);
  console.log(`Initialized data for ${emailRows.length} emails`);
}

// Call the initialize function when the page loads
document.addEventListener("DOMContentLoaded", initializeEmailDataStore);

/**
 * Main function to perform unsubscribe for selected emails
 */
async function performUnsubscribe() {
  const selectedIdsFromStorage = getSelectedEmailsFromStorage(); // Get ALL selected IDs
  if (selectedIdsFromStorage.length === 0) {
    alert("Please select at least one email to unsubscribe.");
    return;
  }

  // Check against the global MAX_EMAILS constant
  if (selectedIdsFromStorage.length > MAX_EMAILS) {
    alert(
      `For reliable processing, please limit your selection to ${MAX_EMAILS} emails at a time. Currently ${selectedIdsFromStorage.length} are selected.`
    );
    return;
  }

  // Map email IDs to their senders and collect all data needed for processing
  const senderMap = {};
  const emailsToProcess = []; // Array of objects: {id, sender, header_link, mailto_link, body_link}
  const emailsForBackend = []; // IDs only

  for (const emailId of selectedIdsFromStorage) {
    // Find the checkbox element on the current page
    const checkbox = document.querySelector(
      `.email-checkbox[value="${emailId}"]`
    );

    if (checkbox) {
      // Checkbox found on page, read attributes directly
      const sender = checkbox.getAttribute("data-sender");
      const headerLink = checkbox.getAttribute("data-header-link");
      const mailtoLink = checkbox.getAttribute("data-mailto-link");
      const bodyLink = checkbox.getAttribute("data-body-link");

      if (!sender) {
        console.warn(
          `Missing sender for email ID: ${emailId} on current page. Adding to backend list.`
        );
        if (!emailsForBackend.includes(emailId)) {
          emailsForBackend.push(emailId);
        }
        continue; // Skip client-side processing
      }

      const emailData = {
        id: emailId,
        sender: sender,
        header_link: headerLink,
        mailto_link: mailtoLink,
        body_link: bodyLink,
      };

      emailsToProcess.push(emailData);

      // Group by sender for the progress modal
      if (!senderMap[sender]) {
        senderMap[sender] = [];
      }
      senderMap[sender].push(emailId);
    } else {
      // Checkbox not found on this page, mark for backend processing
      console.log(
        `Email ID ${emailId} not found on page, adding to backend list.`
      );
      if (!emailsForBackend.includes(emailId)) {
        emailsForBackend.push(emailId);
      }
    }
  }

  const senders = Object.keys(senderMap);
  window.totalSendersToProcess = senders.length;
  window.currentSenderIndex = 0;

  // Include emails not found on the current page in the backend list
  const emailIdsOnCurrentPage = Array.from(
    document.querySelectorAll(".email-checkbox")
  ).map((cb) => cb.value);
  selectedIdsFromStorage.forEach((id) => {
    if (
      !emailIdsOnCurrentPage.includes(id) &&
      !emailsForBackend.includes(id) &&
      !emailsToProcess.some((e) => e.id === id)
    ) {
      if (!emailsForBackend.includes(id)) {
        console.log(`Adding email ID ${id} (not on page) to backend list.`);
        emailsForBackend.push(id);
      }
    }
  });

  const shouldArchive = document.getElementById("archive-toggle").checked;
  const buttonId = "unsubscribe-button";
  setLoading(buttonId, "Processing...");

  // Show progress modal - using senders from client-side emails
  const { links } = showUnsubscribeProgressModal(senders);

  const successfullyProcessedIds = [];
  const manualActions = []; // Array of { message_id, link, type: 'mailto'/'body' }
  const failedEmails = []; // Array of { id, error }
  let archiveStatus = null;

  console.log(`Processing ${emailsToProcess.length} emails client-side.`);

  // Process client-side emails (attempt header links)
  const clientPromises = emailsToProcess.map(async (email) => {
    updateSenderStatus(email.sender, "processing");

    if (email.header_link) {
      // Attempt background request with header_link
      try {
        console.log(
          `Attempting header link for ${email.sender} (${email.id}): ${email.header_link}`
        );
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 sec timeout

        const response = await fetch(email.header_link, {
          method: "GET", // Or POST if header indicates
          mode: "no-cors",
          redirect: "follow",
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        // Assume success if no error (best guess with no-cors)
        successfullyProcessedIds.push(email.id);
        updateSenderStatus(email.sender, "completed");
        console.log(`Header link success (assumed) for ${email.id}`);
        return { success: true, id: email.id };
      } catch (fetchError) {
        console.warn(
          `Header link fetch failed for ${email.id} (${email.header_link}): ${fetchError.message}`
        );
        // Fall through to check for body/mailto link
      }
    }

    // If header link failed or wasn't present, check for body or mailto for manual action
    if (email.body_link) {
      console.log(
        `Header failed/missing, marking for manual body link for ${email.id}: ${email.body_link}`
      );
      manualActions.push({
        message_id: email.id,
        link: email.body_link,
        type: "body",
      });
      updateSenderStatus(email.sender, "manual", {
        link: email.body_link,
        type: "body",
      });
      return {
        manual: true,
        id: email.id,
        link: email.body_link,
        type: "body",
      };
    } else if (email.mailto_link) {
      console.log(
        `Header failed/missing, marking for manual mailto link for ${email.id}: ${email.mailto_link}`
      );
      manualActions.push({
        message_id: email.id,
        link: email.mailto_link,
        type: "mailto",
      });
      updateSenderStatus(email.sender, "manual", {
        link: email.mailto_link,
        type: "mailto",
      });
      return {
        manual: true,
        id: email.id,
        link: email.mailto_link,
        type: "mailto",
      };
    } else {
      // No usable link found client-side
      console.error(`No unsubscribe link found for ${email.id}`);
      failedEmails.push({ id: email.id, error: "No unsubscribe link found" });
      updateSenderStatus(email.sender, "error");
      return { error: true, id: email.id, message: "No link" };
    }
  });

  // Wait for all client-side processing to settle
  await Promise.all(clientPromises);
  console.log("Completed client-side processing.");

  // Update progress based on client-side results
  const clientProcessedCount =
    successfullyProcessedIds.length +
    manualActions.length +
    failedEmails.length;
  updateProgress(clientProcessedCount);

  // Process any emails designated for the backend (e.g., those not on the page)
  if (emailsForBackend.length > 0) {
    console.log(
      `Sending ${emailsForBackend.length} email IDs to backend for processing.`
    );
    const backendFormData = new FormData();
    const backendEmailDetails = getEmailDetailsFromStorage();

    emailsForBackend.forEach((id) => {
      backendFormData.append("email_ids", id);
      // Send link data if available in storage
      const details = backendEmailDetails[id];
      backendFormData.append("header_links", details?.header_link || "null");
      backendFormData.append("body_links", details?.body_link || "null");
      backendFormData.append("mailto_links", details?.mailto_link || "null");
    });
    backendFormData.append("archive", "false"); // Archive handled separately

    try {
      const backendResponse = await fetch(unsubscribeUrl, {
        method: "POST",
        body: backendFormData,
      });
      const backendResult = await backendResponse.json();

      if (backendResponse.ok && backendResult.success) {
        console.log("Backend processing successful:", backendResult.message);
        // Merge backend mailto links into manual actions
        if (backendResult.details && backendResult.details.mailto_links) {
          backendResult.details.mailto_links.forEach((mailtoAction) => {
            // Avoid duplicates if already added from client-side fallback
            if (
              !manualActions.some(
                (m) => m.message_id === mailtoAction.message_id
              )
            ) {
              manualActions.push({ ...mailtoAction, type: "mailto" });
              // Update progress modal if sender is visible
              const sender =
                backendEmailDetails[mailtoAction.message_id]?.sender;
              if (sender) {
                updateSenderStatus(sender, "manual", {
                  link: mailtoAction.link,
                  type: "mailto",
                });
              }
            }
          });
        }
        // Add any newly processed IDs (though backend mainly handles mailto now)
        // We assume backend doesn't auto-process HTTP links anymore
      } else {
        console.error(
          "Backend processing error:",
          backendResult.error || backendResult.message
        );
        // Add backend errors to the list - maybe map to specific email IDs if possible?
        emailsForBackend.forEach((id) =>
          failedEmails.push({
            id: id,
            error: backendResult.error || "Backend processing failed",
          })
        );
      }
    } catch (error) {
      console.error("Error during backend fetch:", error);
      emailsForBackend.forEach((id) =>
        failedEmails.push({ id: id, error: `Network error: ${error.message}` })
      );
    }
  }

  // --- Batch Archive (if requested) ---
  if (shouldArchive && selectedIdsFromStorage.length > 0) {
    console.log(
      `Starting batch archive for ${selectedIdsFromStorage.length} emails.`
    );
    const archiveFormData = new FormData();
    selectedIdsFromStorage.forEach((id) =>
      archiveFormData.append("email_ids", id)
    );

    try {
      const archiveResponse = await fetch(archiveUrl, {
        method: "POST",
        body: archiveFormData,
      });
      const archiveResult = await archiveResponse.json();

      if (archiveResponse.ok && archiveResult.success) {
        console.log("Archive successful:", archiveResult.message);
        archiveStatus = {
          success: true,
          message: archiveResult.message,
          permissionError: false,
        };
      } else {
        console.error(
          "Archive failed:",
          archiveResult.message || archiveResult.error
        );
        const isPermissionError = archiveResponse.status === 403;
        archiveStatus = {
          success: false,
          message: archiveResult.message || "Archive failed.",
          permissionError: isPermissionError,
        };
        // Add archive errors to general errors if desired
        // failedEmails.push({ id: 'archive', error: archiveStatus.message });
      }
    } catch (error) {
      console.error("Error during archive fetch:", error);
      archiveStatus = {
        success: false,
        message: `Network error during archiving: ${error.message}`,
        permissionError: false,
      };
      // failedEmails.push({ id: 'archive', error: archiveStatus.message });
    }
  }

  // --- Finalize and Show Results ---
  // Consolidate processed IDs for UI cleanup
  window.processedEmailIds = [...selectedIdsFromStorage];

  // Final progress update
  const finalProcessedCount =
    successfullyProcessedIds.length +
    manualActions.length +
    failedEmails.length;
  updateProgress(finalProcessedCount);

  // Prepare result data object for the modal
  const finalResultData = {
    processedEmailIds: window.processedEmailIds,
    manualActions: manualActions, // Array: { message_id, link, type }
    errors: failedEmails, // Array: { id, error }
    archiveStatus: archiveStatus, // { success, message, permissionError }
    message: "Processing complete.", // Generic message, detailed counts in modal
  };

  // Show completion modal using the consolidated data
  showModal(renderSuccessModalContent(finalResultData));

  // Store processed senders for UI marking
  storeProcessedSenders(senders);
  markProcessedSenders();

  // Clear selection storage
  saveSelectedEmailsToStorage([]);
  // Do NOT clear email details storage here, needed for modal rendering

  hideLoading(buttonId);
}

/**
 * Perform archive action only (no unsubscribe)
 */
async function performArchiveActionOnly() {
  const selectedIdsFromStorage = getSelectedEmailsFromStorage(); // Get ALL selected IDs
  if (selectedIdsFromStorage.length === 0) {
    alert("Please select at least one email to archive.");
    return;
  }

  // Store the IDs we are about to process for removal later
  window.processedEmailIds = [...selectedIdsFromStorage];

  const buttonId = "archive-only-button";
  setLoading(buttonId, "Archiving...");

  const formData = new FormData();
  // Send ALL selected IDs from storage to the backend
  selectedIdsFromStorage.forEach((id) => formData.append("email_ids", id));

  try {
    const response = await fetch(archiveUrl, {
      method: "POST",
      body: formData,
    });
    const resultData = await response.json(); // Expect JSON

    if (response.ok && resultData.success) {
      showModal(renderSuccessModalContent(resultData.message));
      // Clear storage ONLY on successful processing of ALL items
      saveSelectedEmailsToStorage([]);
      saveEmailDetailsToStorage({});
    } else {
      // Check for permission issues
      if (
        response.status === 403 &&
        resultData.details &&
        resultData.details.reason
      ) {
        // Create a more helpful error message for permission issues
        let permissionMessage =
          resultData.message ||
          "Archiving emails requires additional permissions";
        if (resultData.details.help_text) {
          permissionMessage += "\n\n" + resultData.details.help_text;
        }
        showModal(renderErrorModalContent(permissionMessage));
      } else {
        const errorMessage =
          resultData.error ||
          resultData.message ||
          `Request failed with status ${response.status}`;
        showModal(renderErrorModalContent(errorMessage));
      }
      window.processedEmailIds = []; // Don't remove items or clear storage on failure
    }
  } catch (error) {
    console.error("Error archiving:", error);
    showModal(
      renderErrorModalContent(
        "Network error occurred during archiving. Please try again."
      )
    );
    window.processedEmailIds = [];
  } finally {
    hideLoading(buttonId);
    // Action bar update happens in closeModal or removeProcessedEmails
  }
}

/**
 * Remove all processed emails from the UI
 */
function removeProcessedEmails() {
  const listContainer = document.getElementById("subscription-list");

  // Clear email details storage AFTER modal is closed and emails removed
  saveEmailDetailsToStorage({});

  // Use the stored processedEmailIds set during the action call
  if (window.processedEmailIds && window.processedEmailIds.length > 0) {
    console.log(
      `Removing ${window.processedEmailIds.length} processed emails from view`
    );

    window.processedEmailIds.forEach((emailId) => {
      const emailRow = document.getElementById(`email-${emailId}`);
      if (!emailRow) {
        console.warn(`Could not find email row with ID: email-${emailId}`);
        return;
      }

      const checkbox = emailRow.querySelector(".email-checkbox");
      const sender = checkbox?.dataset.sender;

      // Remove the email row from DOM
      emailRow.remove();
      console.log(`Removed email ID: ${emailId}`);

      // Check if sender group is now empty
      if (sender) {
        // Use the same regex pattern as in other parts of the code
        const senderId = sender
          .replace(/\s+/g, "-")
          .replace(/[<>]/g, "")
          .replace(/@/g, "-")
          .replace(/\./g, "-");

        const senderGroup = document.getElementById(`sender-group-${senderId}`);
        if (!senderGroup) {
          console.warn(
            `Could not find sender group for: ${sender}, ID: ${senderId}`
          );
          return;
        }

        // Check if the email list div exists and has no more email rows
        const emailsDiv = senderGroup.querySelector(".sender-emails");
        if (
          emailsDiv &&
          emailsDiv.querySelectorAll(".email-row").length === 0
        ) {
          senderGroup.remove();
          console.log(`Removed empty sender group: ${sender}`);
        }
      }
    });
    window.processedEmailIds = []; // Clear the list
  }

  // Check if the list is empty AFTER removing items
  if (
    listContainer &&
    listContainer.querySelectorAll(".sender-group").length === 0
  ) {
    console.log("Subscription list is now empty.");
    const scanMoreButton = document.getElementById("scan-more-button");
    if (scanMoreButton) {
      console.log(
        "Next page token exists, automatically clicking 'Scan More Emails'."
      );
      scanMoreButton.click(); // Trigger loading next page
    } else {
      console.log("No next page token, displaying final message.");
      // Display a final message if no more pages
      const contentContainer = document.querySelector(".content-container");
      if (contentContainer) {
        contentContainer.innerHTML = `
                    <div class="card p-8 text-center max-w-lg mx-auto mt-10" style="opacity: 0; animation: scaleIn 0.5s ease forwards; animation-delay: 0.1s;">
                        <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-12 w-12 text-success mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <h3 class="text-lg font-medium text-foreground mb-2">All Done!</h3>
                        <p class="text-muted-foreground mb-6">You've processed all the subscription emails found based on the scan criteria.</p>
                        <a href="/" class="btn btn-outline btn-sm mt-4 focus-ring">Back Home</a>
                    </div>
                `;
      }
    }
  }

  closeModal(); // This calls updateActionBar which reads the (now empty) storage
}

/**
 * Update the status of a sender in the progress list
 */
function updateSenderStatus(sender, status, linkType = null, bodyLink = null) {
  // This function seems to be duplicated or from an older version.
  // The version in scan-results-actions.js should be the primary one.
  // Keeping this commented out for reference if needed.
  /*
  const sendersList = document.getElementById("senders-progress-list");
  if (!sendersList) return;

  // Find or create the sender item
  let senderItem = document.querySelector(
    `.sender-status-item[data-sender="${sender}"]`
  );

  if (!senderItem) {
    senderItem = document.createElement("li");
    senderItem.className =
      "sender-status-item flex items-center justify-between py-1 border-b border-base-300 last:border-0";
    senderItem.setAttribute("data-sender", sender);

    // Truncate sender name if too long
    const displayName =
      sender.length > 25 ? sender.substring(0, 22) + "..." : sender;

    senderItem.innerHTML = `
      <span class="sender-name text-sm">${displayName}</span>
      <span class="sender-status flex items-center">
        <span class="status-indicator mr-2"></span>
        <span class="status-text text-xs"></span>
      </span>
    `;

    sendersList.appendChild(senderItem);
  }

  // Update the status indicator and text
  const statusIndicator = senderItem.querySelector(".status-indicator");
  const statusText = senderItem.querySelector(".status-text");

  // Remove all status classes
  statusIndicator.className = "status-indicator mr-2";

  // Add appropriate status class and text
  if (status === "processing") {
    statusIndicator.classList.add("animate-pulse", "text-warning");
    statusIndicator.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>';
    statusText.textContent = "Processing...";
    statusText.className = "status-text text-xs text-muted-foreground";
  } else if (status === "completed") {
    statusIndicator.classList.add("text-success");
    statusIndicator.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>';
    statusText.textContent = "Done";
    statusText.className = "status-text text-xs text-success";
  } else if (status === "manual") {
    statusIndicator.classList.add("text-warning");
    statusIndicator.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>';
    statusText.textContent = "Manual action";
    statusText.className = "status-text text-xs text-warning";

    // If manual action is required and we have a link type, show a link
    if (linkType === "http" || linkType === "body_link") {
      // If we have a body link that differs from header link, show it as alternative
      if (bodyLink) {
        const linkNote = senderItem.querySelector(".link-note");
        if (!linkNote) {
          const noteElem = document.createElement("div");
          noteElem.className = "link-note text-xs mt-1";
          noteElem.innerHTML = `Try this alternative link: <a href="${bodyLink}" target="_blank" class="text-brand hover:underline">Open</a>`;
          senderItem.appendChild(noteElem);
        }
      }
    }
  } else if (status === "error") {
    statusIndicator.classList.add("text-destructive");
    statusIndicator.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>';
    statusText.textContent = "Error";
    statusText.className = "status-text text-xs text-destructive";
  }
  */
}

// --- Global functions ---
window.performUnsubscribe = performUnsubscribe;
window.performArchiveActionOnly = performArchiveActionOnly;
window.removeProcessedEmails = removeProcessedEmails;
window.setEndpoints = setEndpoints;
