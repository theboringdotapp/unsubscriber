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

  // Map email IDs to their senders for processing
  const senderMap = {};
  const emailsWithNoLinks = [];
  const allEmailDetails = [];

  // Get stored email details for all selected emails
  const storedEmailDetails = getEmailDetailsFromStorage();

  // First analyze all selected emails to categorize them
  for (const emailId of selectedIdsFromStorage) {
    let sender = null;
    let unsubscribeLink = null;
    let emailRow = null;

    // First check if we have the details stored in sessionStorage
    if (storedEmailDetails[emailId]) {
      const details = storedEmailDetails[emailId];
      sender = details.sender;
      unsubscribeLink = details.link;

      console.log(
        `Using stored details for email ${emailId}: sender=${sender}, link=${unsubscribeLink}`
      );
    } else {
      // Fallback to checking the DOM if the email is on the current page
      const checkbox = document.querySelector(
        `.email-checkbox[value="${emailId}"]`
      );

      if (checkbox) {
        // Email is on current page
        sender = checkbox.getAttribute("data-sender");
        emailRow = document.getElementById(`email-${emailId}`);

        // Extract unsubscribe link if available
        // Try to find the link in different ways
        // First check for direct links from email row
        if (emailRow) {
          const linkElements = emailRow.querySelectorAll(
            "a.unsubscribe-link, a.email-link"
          );
          if (linkElements.length > 0) {
            unsubscribeLink = linkElements[0].getAttribute("href");
          }
        }

        // If no link found in email row, try to find sender's primary unsubscribe link
        if (!unsubscribeLink && sender) {
          // Find the sender group element
          const senderId = sender
            .replace(/\s+/g, "-")
            .replace(/[<>]/g, "")
            .replace(/@/g, "-")
            .replace(/\./g, "-");

          const senderGroup = document.getElementById(
            `sender-group-${senderId}`
          );
          if (senderGroup) {
            const headerLinks =
              senderGroup.querySelectorAll(".sender-header a");
            if (headerLinks.length > 0) {
              unsubscribeLink = headerLinks[0].getAttribute("href");
            }
          }
        }

        // Save this info to storage for future use
        if (sender) {
          storedEmailDetails[emailId] = {
            id: emailId,
            sender: sender,
            link: unsubscribeLink,
            type: unsubscribeLink
              ? unsubscribeLink.startsWith("mailto:")
                ? "mailto"
                : "http"
              : null,
          };
          saveEmailDetailsToStorage(storedEmailDetails);
        }
      } else {
        // Email is not on current page and we don't have stored details
        console.log(
          `Email ID ${emailId} not found on current page and no stored details, will be processed by backend`
        );
        emailsWithNoLinks.push(emailId);
        continue;
      }
    }

    if (!sender) {
      console.warn(`Missing sender for email ID: ${emailId}`);
      emailsWithNoLinks.push(emailId);
      continue;
    }

    // Store email details
    const emailDetails = {
      id: emailId,
      sender: sender,
      link: unsubscribeLink,
    };

    allEmailDetails.push(emailDetails);

    // Group by sender
    if (!senderMap[sender]) {
      senderMap[sender] = [];
    }
    senderMap[sender].push(emailId);

    // Track emails with no links
    if (!unsubscribeLink) {
      emailsWithNoLinks.push(emailId);
    }
  }

  const senders = Object.keys(senderMap);
  window.totalSendersToProcess = senders.length;
  window.currentSenderIndex = 0;

  // To handle emails not on the current page, we'll send all IDs to the backend
  // that aren't being processed on the client side
  const shouldArchive = document.getElementById("archive-toggle").checked;
  const buttonId = "unsubscribe-button";

  // Show progress modal and get link maps
  const { httpLinks, mailtoLinks } = showUnsubscribeProgressModal(senders);

  // Process HTTP links on the client side
  const httpSenders = Object.keys(httpLinks);
  const mailtoSenders = Object.keys(mailtoLinks);

  console.log(
    `Processing client-side: ${httpSenders.length} HTTP links, ${mailtoSenders.length} mailto links`
  );
  console.log(
    `${emailsWithNoLinks.length} emails have no direct unsubscribe links or are from other pages`
  );

  const successfullyProcessedIds = [];
  const manuallyRequiredIds = []; // Track IDs requiring manual action
  const failedIds = [];
  const errors = [];
  let lastHttpLink = null;

  // Client-side HTTP link processing
  console.log(
    `Starting to process ${httpSenders.length} HTTP links in parallel`
  );

  // Process all HTTP links concurrently using Promise.all
  const httpPromises = httpSenders.map(async (sender) => {
    const link = httpLinks[sender];
    updateSenderStatus(sender, "processing");

    try {
      console.log(`Processing HTTP link for ${sender}: ${link}`);

      // Store for the modal (prioritize manual links)
      if (!lastHttpLink) {
        lastHttpLink = link;
      }

      let automaticSuccess = false;

      if (link) {
        try {
          // Make a background HTTP request instead of opening a tab
          console.log(`Fetching link in background: ${link}`);

          // Using fetch with a timeout to avoid hanging
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

          const response = await fetch(link, {
            method: "GET",
            mode: "no-cors", // Important for cross-origin requests
            redirect: "follow",
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          // Check if it's likely the unsubscribe was successful
          // In no-cors mode, we don't have full response details, but we can assume success if it didn't throw
          automaticSuccess = true;
          console.log(`Successfully fetched ${link} for ${sender}`);
        } catch (fetchError) {
          console.warn(
            `Fetch request failed for ${link}: ${fetchError.message}`
          );
          automaticSuccess = false;
        }
      }

      // Mark as requiring manual action or automated success
      const senderEmailIds = senderMap[sender] || [];

      if (automaticSuccess) {
        // Automatic success
        senderEmailIds.forEach((id) => {
          if (!successfullyProcessedIds.includes(id)) {
            successfullyProcessedIds.push(id);
          }
        });

        updateSenderStatus(sender, "completed");
      } else {
        // Manual action required
        senderEmailIds.forEach((id) => {
          if (!manuallyRequiredIds.includes(id)) {
            manuallyRequiredIds.push(id);
          }
        });

        // Update UI to show manual action required with link
        updateSenderStatus(sender, "manual", "http");
      }

      window.currentSenderIndex++;
      // Update progress based on the number of emails processed so far
      const processedEmailCount =
        successfullyProcessedIds.length + manuallyRequiredIds.length;
      updateProgress(processedEmailCount);

      return {
        success: automaticSuccess,
        manualRequired: !automaticSuccess,
        sender,
        link,
      };
    } catch (error) {
      console.error(`Error processing HTTP link for ${sender}:`, error);
      errors.push(
        `Failed to process unsubscribe for ${sender}: ${error.message}`
      );
      failedIds.push(...(senderMap[sender] || []));
      updateSenderStatus(sender, "error");

      return { success: false, sender, error };
    }
  });

  // Wait for all HTTP link processing to complete
  await Promise.all(httpPromises);
  console.log(`Completed processing ${httpSenders.length} HTTP links`);

  // Process mailto links and any remaining emails through the backend
  const emailsForBackend = [...emailsWithNoLinks];
  mailtoSenders.forEach((sender) => {
    emailsForBackend.push(...(senderMap[sender] || []));
  });

  // Add any emails from session storage that weren't found on this page
  const emailIdsOnCurrentPage = Array.from(
    document.querySelectorAll(".email-checkbox")
  ).map((cb) => cb.value);
  const emailIdsNotOnPage = selectedIdsFromStorage.filter(
    (id) => !emailIdsOnCurrentPage.includes(id)
  );
  emailIdsNotOnPage.forEach((id) => {
    if (!emailsForBackend.includes(id)) {
      console.log(
        `Adding email ID ${id} from another page to backend processing`
      );
      emailsForBackend.push(id);
    }
  });

  if (emailsForBackend.length > 0) {
    console.log(
      `Sending ${emailsForBackend.length} emails to backend for mailto/server processing`
    );

    const formData = new FormData();
    emailsForBackend.forEach((id) => formData.append("email_ids", id));
    formData.append("archive", "false"); // We'll do batch archiving separately

    try {
      const response = await fetch(unsubscribeUrl, {
        method: "POST",
        body: formData,
      });

      const resultData = await response.json();

      if (response.ok && resultData.success) {
        console.log("Backend processing successful");

        // Add backend-processed IDs to our list
        if (resultData.details && resultData.details.processed_email_ids) {
          resultData.details.processed_email_ids.forEach((id) => {
            if (!successfullyProcessedIds.includes(id)) {
              successfullyProcessedIds.push(id);
            }
          });
        }

        // Update processing status for backend-processed senders
        if (resultData.details && resultData.details.processed_senders) {
          resultData.details.processed_senders.forEach((sender) => {
            updateSenderStatus(sender, "completed");
          });
        }

        // Get any HTTP link from backend
        if (resultData.http_link && !lastHttpLink) {
          lastHttpLink = resultData.http_link;
        }

        // Update progress with the new total processed count
        const processedEmailCount =
          successfullyProcessedIds.length + manuallyRequiredIds.length;
        updateProgress(processedEmailCount);
      } else {
        console.error("Backend processing error:", resultData.error);
        errors.push(resultData.error || "Backend processing failed");

        // Add error details if available
        if (resultData.details) {
          if (resultData.details.unsubscribe_errors) {
            errors.push(...resultData.details.unsubscribe_errors);
          }
        }
      }
    } catch (error) {
      console.error("Error during backend processing:", error);
      errors.push(`Network error during backend processing: ${error.message}`);
    }
  }

  // Ensure all selected emails from storage are included in the processing
  selectedIdsFromStorage.forEach((id) => {
    if (
      !successfullyProcessedIds.includes(id) &&
      !manuallyRequiredIds.includes(id) &&
      !failedIds.includes(id)
    ) {
      // This email wasn't explicitly tracked anywhere, so consider it processed by backend
      successfullyProcessedIds.push(id);
    }
  });

  // Perform batch archive if needed
  if (shouldArchive && selectedIdsFromStorage.length > 0) {
    console.log(`Batch archiving ${selectedIdsFromStorage.length} emails`);

    const formData = new FormData();
    // Always use ALL emails from session storage for archiving
    selectedIdsFromStorage.forEach((id) => formData.append("email_ids", id));

    try {
      const response = await fetch(archiveUrl, {
        // URL should be provided by the template
        method: "POST",
        body: formData,
      });

      const archiveResult = await response.json();

      if (!response.ok || !archiveResult.success) {
        console.error(
          "Archive operation failed:",
          archiveResult.message || archiveResult.error
        );

        // Check for permissions issue (status 403)
        if (
          response.status === 403 &&
          archiveResult.details &&
          archiveResult.details.reason
        ) {
          // This is a permissions issue - show the user a manual archive instruction
          console.log(
            "Permission issue detected:",
            archiveResult.details.reason
          );
          errors.push(archiveResult.message);
          if (archiveResult.details.help_text) {
            errors.push(archiveResult.details.help_text);
          }
        } else if (
          archiveResult.details &&
          archiveResult.details.archive_errors
        ) {
          errors.push(...archiveResult.details.archive_errors);
        } else {
          errors.push("Failed to archive some emails");
        }
      }
    } catch (error) {
      console.error("Error during archive operation:", error);
      errors.push(`Network error during archiving: ${error.message}`);
    }
  }

  // Final update to UI
  // Consider all selected emails as "processed" for UI and cleanup purposes
  window.processedEmailIds = [...selectedIdsFromStorage];

  // Construct final message
  const successCount = successfullyProcessedIds.length;
  const manualCount = manuallyRequiredIds.length;
  const failCount = failedIds.length;

  let message = "";

  if (successCount > 0) {
    message += `Automatically processed ${successCount} email${
      successCount !== 1 ? "s" : ""
    }.`;
  }

  if (manualCount > 0) {
    if (message) message += " ";
    message += `${manualCount} email${
      manualCount !== 1 ? "s" : ""
    } require manual action.`;
  }

  if (failCount > 0) {
    if (message) message += " ";
    message += `${failCount} email${failCount !== 1 ? "s" : ""} failed.`;
  }

  if (shouldArchive) {
    if (message) message += " ";
    const archivedCount = selectedIdsFromStorage.length;
    message += `Archived ${archivedCount} email${
      archivedCount !== 1 ? "s" : ""
    }.`;
  }

  // Get all manual links for display in the result modal
  const manualLinks = {};

  // Collect links for emails requiring manual action
  for (const sender of Object.keys(httpLinks)) {
    if (
      senderMap[sender] &&
      senderMap[sender].some((id) => manuallyRequiredIds.includes(id))
    ) {
      manualLinks[sender] = httpLinks[sender];
    }
  }

  for (const sender of Object.keys(mailtoLinks)) {
    if (
      senderMap[sender] &&
      senderMap[sender].some((id) => manuallyRequiredIds.includes(id))
    ) {
      manualLinks[sender] = mailtoLinks[sender];
    }
  }

  const resultData = {
    success: failCount === 0,
    message: message.trim(),
    details: {
      unsubscribe_errors: errors,
      processed_senders: senders,
      processed_email_ids: window.processedEmailIds,
      manual_links: manualLinks,
      manual_count: manualCount,
    },
    http_link: lastHttpLink,
    has_manual_actions: manualCount > 0,
  };

  // Final progress update to ensure progress bar is complete
  const finalProcessedCount =
    successfullyProcessedIds.length + manuallyRequiredIds.length;
  updateProgress(finalProcessedCount);

  // Show completion modal
  showModal(
    renderSuccessModalContent(
      resultData.message,
      resultData.http_link,
      resultData
    )
  );

  // Store the senders that were part of this batch
  storeProcessedSenders(senders);
  markProcessedSenders(); // Immediately mark them on the current page

  // Clear selection storage on successful processing
  saveSelectedEmailsToStorage([]);
  saveEmailDetailsToStorage({});

  // Hide loading state on button
  const button = document.getElementById(buttonId);
  if (button) {
    button.disabled = false;
    if (button.classList.contains("is-loading")) {
      // If using the common loading function
      hideLoading(buttonId);
    } else {
      // Manual reset
      button.classList.remove("opacity-50", "cursor-not-allowed");
      button.textContent = "Unsubscribe";
    }
  }
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

// --- Global functions ---
window.performUnsubscribe = performUnsubscribe;
window.performArchiveActionOnly = performArchiveActionOnly;
window.removeProcessedEmails = removeProcessedEmails;
window.setEndpoints = setEndpoints;
