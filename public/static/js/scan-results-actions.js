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

  // Get links from selected email details
  const links = {}; // Structure: { sender: { header: [], mailto: [], body: [] } }
  const storedEmailDetails = getEmailDetailsFromStorage(); // Assumes this holds {id: {sender, header_link, mailto_link, body_link}}
  let totalEmails = 0;

  // Generate a list of senders with progress indicators
  senders.forEach((sender, index) => {
    links[sender] = { header: [], mailto: [], body: [] };
    let senderEmailCount = 0;

    // Iterate through ALL stored details to find emails for this sender
    Object.values(storedEmailDetails).forEach((detail) => {
      if (detail.sender === sender) {
        // Only count emails actually selected
        const selectedIds = getSelectedEmailsFromStorage();
        if (selectedIds.includes(detail.id)) {
          senderEmailCount++;
          if (detail.header_link) links[sender].header.push(detail.header_link);
          if (detail.mailto_link) links[sender].mailto.push(detail.mailto_link);
          if (detail.body_link) links[sender].body.push(detail.body_link);
        }
      }
    });

    totalEmails += senderEmailCount;

    // Use the first available link for display (if any) - prefer header > mailto > body
    const firstHeader =
      links[sender].header.length > 0 ? links[sender].header[0] : null;
    const firstMailto =
      links[sender].mailto.length > 0 ? links[sender].mailto[0] : null;
    const firstBody =
      links[sender].body.length > 0 ? links[sender].body[0] : null;
    const displayLink = firstHeader || firstMailto || firstBody;

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
                 <svg class="error-icon w-4 h-4 text-destructive hidden" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                   <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                 </svg>
                <a href="#" class="action-button hidden text-xs btn" data-link="${
                  displayLink || "#"
                }">&nbsp;</a>
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
            <span>Automatic Unsubscribe (Header Link)</span>
        </div>
        <div class="flex items-center text-sm">
            <svg class="warning-icon w-4 h-4 text-warning mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>
            <span>Manual Action Needed (Mailto / Body Link / Failed Header)</span>
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
                <span id="progress-text">0/${totalEmails.toString()} emails</span>
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

  // Store total emails to process for progress calculation
  window.totalEmailsToProcess = totalEmails;

  // Start the first item as processing
  if (senders.length > 0) {
    updateSenderStatus(senders[0], "processing");
  }

  // Return the link maps for use in processing
  return { links };
}

// Update progress indicator
function updateProgress(completedCount) {
  // Use the emails count if available, otherwise fall back to sender count
  const totalCount =
    window.totalEmailsToProcess || window.totalSendersToProcess || 1;
  const progressPercent = Math.min(
    100,
    Math.floor((completedCount / totalCount) * 100)
  );

  // Update the progress bar
  const progressBar = document.getElementById("progress-bar");
  const progressText = document.getElementById("progress-text");
  const progressPercentage = document.getElementById("progress-percentage");

  if (progressBar) progressBar.style.width = `${progressPercent}%`;
  if (progressText) {
    const displayCount = Math.min(Math.floor(completedCount), totalCount);
    progressText.innerText = `${displayCount}/${totalCount} emails`;
  }
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
function updateSenderStatus(sender, status, linkInfo = null) {
  const senderItem = document.querySelector(
    `.sender-progress-item[data-sender=\"${sender}\"]`
  );
  if (!senderItem) return;

  const statusText = senderItem.querySelector(".status-text");
  const spinner = senderItem.querySelector(".loading-spinner");
  const checkIcon = senderItem.querySelector(".check-icon");
  const warningIcon = senderItem.querySelector(".warning-icon");
  const errorIcon = senderItem.querySelector(".error-icon"); // Add error icon selector
  const actionButton = senderItem.querySelector(".action-button");

  // Reset all indicators
  spinner.classList.add("hidden");
  checkIcon.classList.add("hidden");
  warningIcon?.classList.add("hidden");
  errorIcon?.classList.add("hidden"); // Hide error icon
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
    if (statusText) statusText.innerText = "Manual Action";
    if (warningIcon) warningIcon.classList.remove("hidden");
    if (actionButton && linkInfo) {
      actionButton.classList.remove("hidden");
      actionButton.href = linkInfo.link;
      actionButton.target = "_blank";
      actionButton.classList.add("btn-sm", "btn-outline-warning");
      actionButton.textContent =
        linkInfo.type === "mailto" ? "Send Email" : "Open Link";
    }
  } else if (status === "error") {
    if (statusText) statusText.innerText = "Failed";
    if (errorIcon) errorIcon.classList.remove("hidden"); // Show error icon
  }
}

// Render success modal content
function renderSuccessModalContent(resultData = {}) {
  console.log("Rendering success modal with resultData:", resultData);

  const message = resultData.message || "Operation completed successfully.";
  const processedEmailIds = resultData.processedEmailIds || [];
  const manualActions = resultData.manualActions || []; // Expected: [{sender, link, type: 'mailto'/'body'}]
  const errors = resultData.errors || [];
  const archiveStatus = resultData.archiveStatus || null; // { success: bool, message: str, permissionError: bool }

  let successCount = 0;
  let manualCount = manualActions.length;
  let errorCount = errors.length;
  let archivedCount = 0;

  // Calculate counts based on processedEmailIds and manualActions/errors
  // Assume any ID not in manual or errors was successful
  const manualOrErrorIds = new Set([
    ...manualActions.map((a) => a.message_id),
    ...errors.map((e) => e.id || null),
  ]);
  successCount = processedEmailIds.filter(
    (id) => !manualOrErrorIds.has(id)
  ).length;

  if (archiveStatus && archiveStatus.success) {
    archivedCount = processedEmailIds.length; // Assuming all processed were archived if requested
  }

  // --- Build Sender Summary ---
  let senderSummary = "";
  if (processedEmailIds.length > 0) {
    const senderMap = {}; // Group emails by sender for display
    const storedDetails = getEmailDetailsFromStorage();

    processedEmailIds.forEach((id) => {
      if (storedDetails[id]) {
        const sender = storedDetails[id].sender;
        if (!senderMap[sender]) {
          senderMap[sender] = {
            emails: [],
            status: "success",
            manualLink: null,
            manualType: null,
          };
        }
        senderMap[sender].emails.push(id);

        // Check if this sender requires manual action
        const manualAction = manualActions.find(
          (action) => action.message_id === id
        );
        if (manualAction) {
          senderMap[sender].status = "manual";
          senderMap[sender].manualLink = manualAction.link;
          senderMap[sender].manualType = manualAction.type;
        }
        // Could add error status here too if errors have sender info
      }
    });

    const senders = Object.keys(senderMap).sort(); // Sort senders alphabetically
    const maxSendersToShow = 10; // Limit display
    let displayedSenders = senders.slice(0, maxSendersToShow);
    let remainingSenders = senders.length - displayedSenders.length;

    let sendersListHtml = displayedSenders
      .map((sender) => {
        const senderData = senderMap[sender];
        const status = senderData.status;
        const manualLink = senderData.manualLink;
        const manualType = senderData.manualType;
        let statusIcon = "";
        let actionButton = "";

        if (status === "success") {
          statusIcon = `<svg class="w-4 h-4 text-success mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>`;
        } else if (status === "manual" && manualLink) {
          statusIcon = `<svg class="w-4 h-4 text-warning mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>`;
          const buttonText =
            manualType === "mailto" ? "Send Email" : "Open Link";
          const buttonClass =
            manualType === "mailto" ? "text-amber-600" : "text-brand";
          const buttonIcon =
            manualType === "mailto"
              ? `<svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>`
              : `<svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>`;

          actionButton = `<a href="${manualLink}" target="_blank" class="text-xs ${buttonClass} hover:underline ml-2 flex items-center">${buttonIcon}${buttonText}</a>`;
        }
        // Add error status handling if needed

        return `<li class="text-sm text-foreground py-1 flex items-center justify-between">
                        <div class="flex items-center">
                            ${statusIcon}
                            <span class="truncate max-w-[200px]" title="${sender}">${sender}</span>
                        </div>
                        ${actionButton}
                    </li>`;
      })
      .join("");

    if (remainingSenders > 0) {
      sendersListHtml += `<li class="text-sm text-muted-foreground py-1">And ${remainingSenders} more sender${
        remainingSenders > 1 ? "s" : ""
      }...</li>`;
    }

    const summaryTitle =
      manualCount > 0
        ? "Processed Senders (⚠️ some require manual action):"
        : "Processed Senders:";
    senderSummary = `
            <div class="mt-4 text-left w-full">
                <h4 class="text-sm font-medium text-foreground mb-1">${summaryTitle}</h4>
                <ul class="border border-border rounded-md p-2 max-h-60 overflow-y-auto">
                    ${sendersListHtml}
                </ul>
            </div>`;
  }

  // --- Build Manual Action Section (if needed) ---
  let manualActionSection = "";
  if (manualCount > 0) {
    const mailtoActions = manualActions.filter((a) => a.type === "mailto");
    let mailtoInstructions = "";
    if (mailtoActions.length > 0) {
      mailtoInstructions = `
                <div class="mt-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded text-xs">
                    <h5 class="font-medium text-amber-800 dark:text-amber-300 mb-1">For Email Unsubscribe Links:</h5>
                    <ol class="list-decimal pl-5 text-amber-700 dark:text-amber-400 space-y-1">
                        <li>Click the "Send Email" button next to the sender name.</li>
                        <li>Your email client will open with a pre-filled message.</li>
                        <li>Send the email without changing the subject or body.</li>
                    </ol>
                </div>`;
    }

    manualActionSection = `
            <div class="mt-4 p-4 border border-warning rounded-md bg-warning/5 text-sm w-full">
                <div class="flex items-start">
                    <svg class="w-5 h-5 text-warning mr-2 mt-0.5 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                    <div>
                        <h4 class="font-medium text-warning-foreground mb-1">Manual Action Needed (${manualCount})</h4>
                        <p class="mb-3 text-muted-foreground">Some unsubscribe requests couldn't be processed automatically (e.g., failed header requests, mailto links, or body links). Please use the links next to each sender above to complete the process.</p>
                         ${mailtoInstructions}
                    </div>
                </div>
            </div>`;
  }

  // --- Build Error Section (if needed) ---
  let errorSection = "";
  if (errorCount > 0) {
    const errorList = errors
      .map(
        (err) =>
          `<li class="text-xs">${err.message || JSON.stringify(err)}</li>`
      )
      .join("");
    errorSection = `
            <div class="mt-4 p-4 border border-destructive rounded-md bg-destructive/5 text-sm w-full">
                 <div class="flex items-start">
                    <svg class="w-5 h-5 text-destructive mr-2 mt-0.5 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293z" clip-rule="evenodd" /></svg>
                    <div>
                        <h4 class="font-medium text-destructive-foreground mb-1">Errors Occurred (${errorCount})</h4>
                        <ul class="list-disc pl-5 text-muted-foreground space-y-1">${errorList}</ul>
                    </div>
                </div>
            </div>`;
  }

  // --- Build Archive Status Section ---
  let archiveSection = "";
  if (archiveStatus) {
    const icon = archiveStatus.success
      ? `<svg class="w-4 h-4 text-success mr-2 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>`
      : `<svg class="w-4 h-4 ${
          archiveStatus.permissionError ? "text-warning" : "text-destructive"
        } mr-2 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>`;
    const textColor = archiveStatus.success
      ? "text-foreground"
      : archiveStatus.permissionError
      ? "text-warning-foreground"
      : "text-destructive-foreground";

    archiveSection = `
        <div class="mt-4 text-left w-full text-sm">
             <div class="flex items-center ${textColor}">
                ${icon}
                <span>${archiveStatus.message}</span>
            </div>
        </div>`;
  }

  // --- Determine Overall Status Icon & Title ---
  const overallStatus =
    errorCount === 0 && manualCount === 0
      ? "success"
      : errorCount > 0
      ? "error"
      : "warning"; // Manual actions needed

  const iconHtml =
    overallStatus === "success"
      ? `<div class="checkmark-container mb-4"><svg class="checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52"><circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none"/><path class="checkmark-check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/></svg></div>`
      : overallStatus === "warning"
      ? `<div class="warning-container mb-4"><svg class="warning-large" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52" fill="none" stroke="#ffcc00" stroke-width="2"><circle cx="26" cy="26" r="24" fill="none"/><path d="M26 15v15" stroke-linecap="round"/><circle cx="26" cy="37" r="2" fill="#ffcc00"/></svg></div>`
      : `<div class="error-container mb-4"><svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-destructive" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg></div>`;

  const titleHtml =
    overallStatus === "success"
      ? `<h3 class="text-xl font-semibold text-success mb-2">Success!</h3>`
      : overallStatus === "warning"
      ? `<h3 class="text-xl font-semibold text-warning mb-2">Action Required</h3>`
      : `<h3 class="text-xl font-semibold text-destructive mb-2">Processing Complete (with Errors)</h3>`;

  const finalMessage =
    message ||
    (overallStatus === "success"
      ? "Requests processed successfully."
      : "Processing complete. See details below.");

  return `
    <div class="bg-background rounded-lg p-6 flex flex-col items-center">
        <div class="text-center flex flex-col items-center">
            ${iconHtml}
            ${titleHtml}
            <p class="text-foreground">${finalMessage}</p>
        </div>
        
        ${senderSummary}
        ${manualActionSection}
        ${errorSection}
        ${archiveSection} 
        
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
