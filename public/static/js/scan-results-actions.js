/**
 * Core action functionality for scan results page
 */

// --- Utility functions for actions ---
function getSenderMap() {
  const senderMap = {};
  for (const emailId of window.processedEmailIds || []) {
    const checkbox = document.querySelector(
      `.email-checkbox[value="${emailId}"]`
    );
    if (checkbox) {
      const sender = checkbox.getAttribute("data-sender");
      if (sender) {
        if (!senderMap[sender]) {
          senderMap[sender] = [];
        }
        senderMap[sender].push(emailId);
      }
    }
  }
  return senderMap;
}

// Show unsubscribe progress modal and return links
function showUnsubscribeProgressModal(senders) {
  const totalSenders = senders.length;
  let sendersHtml = "";

  // Get HTTP links from sender map
  const httpLinks = {};
  const mailtoLinks = {};

  // Generate a list of senders with progress indicators
  senders.forEach((sender, index) => {
    // Store link info for each sender
    const senderId = sender
      .replace(/\s+/g, "-")
      .replace(/[<>]/g, "")
      .replace(/@/g, "-")
      .replace(/\./g, "-");

    const senderGroup = document.getElementById(`sender-group-${senderId}`);
    let link = "";
    let linkType = "";

    if (senderGroup) {
      const headerLinks = senderGroup.querySelectorAll(".sender-header a");
      if (headerLinks.length > 0) {
        link = headerLinks[0].getAttribute("href") || "";
        linkType = link.startsWith("mailto:") ? "mailto" : "http";

        if (linkType === "mailto") {
          mailtoLinks[sender] = link;
        } else if (linkType === "http") {
          httpLinks[sender] = link;
        }
      }
    }

    sendersHtml += `
        <div class="sender-progress-item flex items-center justify-between py-2 border-b border-border last:border-0" data-sender="${sender}">
            <span class="text-sm text-foreground truncate max-w-[200px]" title="${sender}">${sender}</span>
            <span class="status-indicator flex items-center gap-2">
                <span class="status-text text-xs text-muted-foreground mr-1">Waiting</span>
                <div class="loading-spinner w-4 h-4 hidden">
                    <svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </div>
                <svg class="check-icon w-4 h-4 text-success hidden" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                </svg>
                <svg class="warning-icon w-4 h-4 text-warning hidden" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                </svg>
                <a href="#" class="action-button hidden text-xs btn" data-link="${link}">&nbsp;</a>
            </span>
        </div>`;
  });

  // Add explanation about manual action requirement
  const explanationNote = `
    <div class="mb-3 text-xs text-foreground">
        <div class="flex items-center mb-2 text-sm">
            <svg class="check-icon w-4 h-4 text-success mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
            <span>Automatic Unsubscribe</span>
        </div>
        <div class="flex items-center text-sm">
            <svg class="warning-icon w-4 h-4 text-warning mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>
            <span>Manual Action Required</span>
        </div>
    </div>`;

  const progressModalHtml = `
    <div class="bg-background rounded-lg p-6">
        <div class="mb-4 text-center">
            <h3 class="text-xl font-semibold text-foreground">Unsubscribing...</h3>
            <p class="text-sm text-muted-foreground mt-2">Processing unsubscribe requests for selected emails.</p>
        </div>
        
        <div class="relative pt-1 mb-4">
            <div class="w-full bg-muted rounded-full">
                <div id="progress-bar" class="bg-brand h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
            </div>
            <div class="flex justify-between text-xs text-muted-foreground mt-1">
                <span id="progress-text">0/${totalSenders} senders</span>
                <span id="progress-percentage">0%</span>
            </div>
        </div>
        
        ${explanationNote}
        
        <div class="max-h-60 overflow-y-auto border border-border rounded-md p-2">
            <div id="sender-progress-list">
                ${sendersHtml}
            </div>
        </div>
    </div>`;

  showModal(progressModalHtml);

  // Start the first item as processing
  if (senders.length > 0) {
    updateSenderStatus(senders[0], "processing");
  }

  // Return the link maps for use in processing
  return { httpLinks, mailtoLinks };
}

// Update progress indicator
function updateProgress(completedCount) {
  const totalCount = window.totalSendersToProcess || 1;
  const progressPercent = Math.floor((completedCount / totalCount) * 100);

  // Update the progress bar
  const progressBar = document.getElementById("progress-bar");
  const progressText = document.getElementById("progress-text");
  const progressPercentage = document.getElementById("progress-percentage");

  if (progressBar) progressBar.style.width = `${progressPercent}%`;
  if (progressText)
    progressText.innerText = `${Math.floor(
      completedCount
    )}/${totalCount} senders`;
  if (progressPercentage) progressPercentage.innerText = `${progressPercent}%`;

  // Mock the progress of sender processing for visual feedback
  const senders = Object.keys(getSenderMap());

  if (window.currentSenderIndex < senders.length) {
    // Update the current sender to 'processing'
    const currentSender = senders[window.currentSenderIndex];
    updateSenderStatus(currentSender, "processing");

    // Mark previous senders as 'completed'
    if (window.currentSenderIndex > 0) {
      const previousSender = senders[window.currentSenderIndex - 1];
      updateSenderStatus(previousSender, "completed");
      window.currentSenderIndex++;
    } else {
      window.currentSenderIndex++;
    }
  }
}

// Update the status of a sender in the progress UI
function updateSenderStatus(sender, status, linkType = null) {
  const senderItem = document.querySelector(
    `.sender-progress-item[data-sender="${sender}"]`
  );
  if (!senderItem) return;

  const statusText = senderItem.querySelector(".status-text");
  const spinner = senderItem.querySelector(".loading-spinner");
  const checkIcon = senderItem.querySelector(".check-icon");
  const warningIcon = senderItem.querySelector(".warning-icon");
  const actionButton = senderItem.querySelector(".action-button");

  // Reset all indicators
  spinner.classList.add("hidden");
  checkIcon.classList.add("hidden");
  warningIcon?.classList.add("hidden");
  if (actionButton) actionButton.classList.add("hidden");

  if (status === "waiting") {
    if (statusText) statusText.innerText = "Waiting";
  } else if (status === "processing") {
    if (statusText) statusText.innerText = "Processing";
    spinner.classList.remove("hidden");
  } else if (status === "completed") {
    if (statusText) statusText.innerText = "Completed";
    checkIcon.classList.remove("hidden");
  } else if (status === "manual") {
    if (statusText) statusText.innerText = "Manual Action Required";
    if (warningIcon) warningIcon.classList.remove("hidden");
    if (actionButton) {
      actionButton.classList.remove("hidden");
      // If we stored the link with the button, set it to be openable
      if (actionButton.dataset.link && linkType) {
        actionButton.href = actionButton.dataset.link;
        actionButton.target = "_blank";
        actionButton.classList.add("btn-sm", "btn-outline-warning");
        actionButton.textContent =
          linkType === "mailto" ? "Send Email" : "Open Link";
      }
    }
  } else if (status === "error") {
    if (statusText) statusText.innerText = "Failed";
    if (warningIcon) warningIcon.classList.remove("hidden");
  }
}

// Render success modal content
function renderSuccessModalContent(
  message,
  http_link = null,
  resultData = null
) {
  console.log("Rendering success modal with:", {
    message,
    http_link,
    resultData,
  });

  // Get the list of senders that were processed
  let senders = [];
  let processedEmailIds = [];
  let manualLinks = {};
  let manualCount = 0;

  // First try to use the backend-provided processed senders list
  if (resultData && resultData.details) {
    if (resultData.details.processed_senders) {
      senders = resultData.details.processed_senders;
      console.log(
        `Found ${senders.length} processed senders from backend data`
      );
    }

    // If server returned processed email IDs, use those
    if (resultData.details.processed_email_ids) {
      processedEmailIds = resultData.details.processed_email_ids;
      console.log(
        `Found ${processedEmailIds.length} processed email IDs from backend data`
      );
      // Update the window.processedEmailIds to ensure we only remove properly processed emails
      window.processedEmailIds = processedEmailIds;
    }

    // Get manual links if available
    if (resultData.details.manual_links) {
      manualLinks = resultData.details.manual_links;
    }

    if (resultData.details.manual_count) {
      manualCount = resultData.details.manual_count;
    }
  }

  // Fall back to client-side tracking if backend data not available
  if (senders.length === 0) {
    const senderMap = getSenderMap();
    senders = Object.keys(senderMap);
    console.log(`Using client-side fallback, found ${senders.length} senders`);
  }

  // Prepare a summary of processed senders
  let senderSummary = "";
  if (senders.length > 0) {
    const maxSendersToShow = 5; // Limit the number of senders shown to avoid cluttering the modal

    // Separate senders requiring manual action from those that don't
    const manualSenders = senders.filter(
      (sender) => manualLinks && manualLinks[sender]
    );
    const autoSenders = senders.filter(
      (sender) => !(manualLinks && manualLinks[sender])
    );

    // Always show all manual senders, then fill remaining slots with automatic ones
    let displayedManualSenders = manualSenders;
    let displayedAutoSenders = autoSenders.slice(
      0,
      Math.max(0, maxSendersToShow - displayedManualSenders.length)
    );

    // Combine both lists, prioritizing manual senders
    const displayedSenders = [
      ...displayedManualSenders,
      ...displayedAutoSenders,
    ];
    const remainingSenders = senders.length - displayedSenders.length;

    let sendersList = displayedSenders
      .map((sender) => {
        // Check if this sender requires manual action
        const requiresManual = manualLinks && manualLinks[sender];
        const isMailto =
          requiresManual && manualLinks[sender].startsWith("mailto:");
        const linkType = isMailto ? "Email" : "Link";

        return `<li class="text-sm text-foreground py-1 flex items-center justify-between">
                <div class="flex items-center">
                    ${
                      requiresManual
                        ? `<svg class="w-4 h-4 text-warning mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                        </svg>`
                        : `<svg class="w-4 h-4 text-success mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                        </svg>`
                    }
                    <span class="truncate max-w-[200px]" title="${sender}">${sender}</span>
                </div>
                ${
                  requiresManual && manualLinks[sender]
                    ? `<a href="${
                        manualLinks[sender]
                      }" target="_blank" class="text-xs ${
                        isMailto ? "text-amber-600" : "text-brand"
                      } hover:underline ml-2 flex items-center">
                        ${
                          isMailto
                            ? `<svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>`
                            : `<svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>`
                        }
                        ${linkType}
                    </a>`
                    : ""
                }
            </li>`;
      })
      .join("");

    if (remainingSenders > 0) {
      // Only show the "And X more senders" if there are no manual senders left in the remaining ones
      const remainingManualSenders =
        manualSenders.length - displayedManualSenders.length;
      if (remainingManualSenders === 0) {
        sendersList += `<li class="text-sm text-muted-foreground py-1">And ${remainingSenders} more sender${
          remainingSenders > 1 ? "s" : ""
        }...</li>`;
      }
    }

    const summaryTitle =
      manualCount > 0
        ? "Processed senders (⚠️ some require manual action):"
        : "Processed senders:";

    senderSummary = `
        <div class="mt-4 text-left w-full">
            <h4 class="text-sm font-medium text-foreground mb-1">${summaryTitle}</h4>
            <ul class="border border-border rounded-md p-2 max-h-60 overflow-y-auto">
                ${sendersList}
            </ul>
        </div>`;
  }

  // Include manual action section if needed
  let manualActionSection = "";

  if (manualCount > 0) {
    // Count manual links types
    const httpLinkCount = Object.values(manualLinks).filter((link) =>
      link.startsWith("http")
    ).length;
    const mailtoLinkCount = Object.values(manualLinks).filter((link) =>
      link.startsWith("mailto")
    ).length;

    // Create email-specific instructions if we have mailto links
    let mailtoInstructions = "";
    if (mailtoLinkCount > 0) {
      mailtoInstructions = `
            <div class="mt-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded text-xs">
                <h5 class="font-medium text-amber-800 dark:text-amber-300 mb-1">For Email Unsubscribe Links:</h5>
                <ol class="list-decimal pl-5 text-amber-700 dark:text-amber-400 space-y-1">
                    <li>Click the "Email" button next to the sender name</li>
                    <li>Your email client will open with a pre-addressed message</li>
                    <li>Send the email without changing the subject or content</li>
                </ol>
            </div>`;
    }

    manualActionSection = `
        <div class="mt-4 p-4 border border-warning rounded-md bg-warning/5 text-sm w-full">
            <div class="flex items-start">
                <svg class="w-5 h-5 text-warning mr-2 mt-0.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                </svg>
                <div>
                    <h4 class="font-medium text-warning-foreground mb-1">Manual Action Required</h4>
                    <p class="mb-3 text-muted-foreground">Some unsubscribe requests couldn't be processed automatically. Please use the links next to each sender to complete the unsubscription.</p>
                    <div class="flex flex-wrap gap-2 text-xs">
                        ${
                          httpLinkCount > 0
                            ? `<span class="inline-flex items-center px-2 py-1 rounded-full bg-warning/10 text-warning-foreground">
                                <svg class="w-3 h-3 mr-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101" />
                                </svg>
                                ${httpLinkCount} Web Link${
                                httpLinkCount !== 1 ? "s" : ""
                              }
                            </span>`
                            : ""
                        }
                        ${
                          mailtoLinkCount > 0
                            ? `<span class="inline-flex items-center px-2 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300">
                                <svg class="w-3 h-3 mr-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                </svg>
                                ${mailtoLinkCount} Email Link${
                                mailtoLinkCount !== 1 ? "s" : ""
                              }
                            </span>`
                            : ""
                        }
                    </div>
                    ${mailtoInstructions}
                </div>
            </div>
        </div>`;
  }

  // Determine what icon to show in the header
  const iconHtml =
    manualCount > 0
      ? `<div class="warning-container mb-4">
            <svg class="warning-large" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52" fill="none" stroke="#ffcc00" stroke-width="2">
                <circle cx="26" cy="26" r="24" fill="none"/>
                <path d="M26 15v15" stroke-linecap="round"/>
                <circle cx="26" cy="37" r="2" fill="#ffcc00"/>
            </svg>
        </div>`
      : `<div class="checkmark-container mb-4">
            <svg class="checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                <circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none"/>
                <path class="checkmark-check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
            </svg>
        </div>`;

  const titleHtml =
    manualCount > 0
      ? `<h3 class="text-xl font-semibold text-warning mb-2">Action Required</h3>`
      : `<h3 class="text-xl font-semibold text-success mb-2">Success!</h3>`;

  return `
    <div class="bg-background rounded-lg p-6 flex flex-col items-center">
        <div class="text-center flex flex-col items-center">
            ${iconHtml}
            ${titleHtml}
            <p class="text-foreground">${
              message || "Operation completed successfully."
            }</p>
        </div>
        
        ${senderSummary}
        ${manualActionSection}
        
        <button 
            class="mt-6 btn btn-brand btn-sm focus-ring w-full"
            onclick="window.removeProcessedEmails()">
            Done
        </button>
    </div>`;
}

// Render error modal content
function renderErrorModalContent(message) {
  return `
    <div class="bg-background rounded-lg p-6 text-center flex flex-col items-center">
        <div class="error-container mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-destructive" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
        </div>
        <h3 class="text-xl font-semibold text-destructive mb-2">Error</h3>
        <p class="text-muted-foreground">${message}</p>
        <button 
            class="mt-4 btn btn-outline btn-sm focus-ring"
            onclick="closeModal()">
            Close
        </button>
    </div>`;
}

// --- Global functions ---
window.renderSuccessModalContent = renderSuccessModalContent;
window.renderErrorModalContent = renderErrorModalContent;
window.showUnsubscribeProgressModal = showUnsubscribeProgressModal;
window.updateProgress = updateProgress;
window.updateSenderStatus = updateSenderStatus;
