/**
 * UI interaction handling for scan results page
 */

// --- Initialization ---
document.addEventListener("DOMContentLoaded", function () {
  loadSelectionFromStorage(); // Check boxes based on storage
  updateActionBar(); // Initial action bar update based on storage
  markProcessedSenders(); // Mark senders processed in this session

  // Add visible class to fixed action bar after a short delay
  setTimeout(() => {
    const actionBar = document.getElementById("fixed-action-bar");
    if (actionBar) {
      actionBar.classList.add("visible");
    }
  }, 600);

  // Add event listeners for the select all on page button
  const selectAllButton = document.querySelector(
    'a[onclick="selectAllOnPage(); return false;"]'
  );
  if (selectAllButton) {
    selectAllButton.addEventListener("click", function (e) {
      e.preventDefault();
      selectAllOnPage();
      return false;
    });
  }

  // Add event listener for reset selection button
  const resetButton = document.querySelector(
    'button[onclick="resetSelection()"]'
  );
  if (resetButton) {
    resetButton.addEventListener("click", resetSelection);
  }

  // Add event listener for unsubscribe button
  const unsubscribeButton = document.getElementById("unsubscribe-button");
  if (unsubscribeButton) {
    unsubscribeButton.addEventListener("click", performUnsubscribe);
  }

  // Add listeners for permission modal
  const enableArchivingLinks = document.querySelectorAll(
    'a[onclick="showPermissionModal(); return false;"]'
  );
  enableArchivingLinks.forEach((link) => {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      showPermissionModal();
      return false;
    });
  });

  const closePermissionButton = document.querySelector(
    'button[onclick="closePermissionModal()"]'
  );
  if (closePermissionButton) {
    closePermissionButton.addEventListener("click", closePermissionModal);
  }
});

// Check checkboxes on the current page based on stored IDs
function loadSelectionFromStorage() {
  const selectedIds = getSelectedEmailsFromStorage();
  if (selectedIds.length === 0) return;

  selectedIds.forEach((emailId) => {
    const checkbox = document.querySelector(
      `.email-checkbox[value="${emailId}"]`
    );
    if (checkbox) {
      checkbox.checked = true;
      // Also update the row's selected state
      const emailRow = document.getElementById(`email-${emailId}`);
      if (emailRow) {
        emailRow.classList.add("email-selected");
      }
    }
  });
  // After checking individual boxes, update sender checkboxes state
  updateAllSenderCheckboxes();
}

function markProcessedSenders() {
  const processedSenders = getProcessedSenders();
  if (processedSenders.length === 0) return;

  console.log("Marking processed senders:", processedSenders);

  document.querySelectorAll(".sender-group").forEach((group) => {
    const senderName = group.getAttribute("data-sender");
    if (senderName && processedSenders.includes(senderName)) {
      const senderNameContainer = group.querySelector(".sender-name-container");
      if (
        senderNameContainer &&
        !senderNameContainer.querySelector(".processed-indicator-tooltip")
      ) {
        // Add a tooltip structure around the checkmark
        const tooltipWrapper = document.createElement("span");
        tooltipWrapper.classList.add(
          "processed-indicator-tooltip",
          "tooltip",
          "ml-2"
        ); // Use existing tooltip class

        const iconSpan = document.createElement("span");
        iconSpan.classList.add(
          "tooltip-icon-placeholder",
          "text-muted-foreground"
        ); // Placeholder, maybe style differently
        iconSpan.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                `;

        const tooltipText = document.createElement("span");
        tooltipText.classList.add("tooltip-text"); // Use existing tooltip style
        tooltipText.textContent = "Already Unsubscribed";

        tooltipWrapper.appendChild(iconSpan);
        tooltipWrapper.appendChild(tooltipText);

        senderNameContainer.appendChild(tooltipWrapper);
      }
    }
  });
}

// --- Sender & Email Interaction ---
function toggleCollapse(senderId, button) {
  const emailsDiv = document.getElementById(`emails-${senderId}`);
  const icon = button.querySelector(".chevron-icon");
  emailsDiv.classList.toggle("collapsed");
  if (emailsDiv.classList.contains("collapsed")) {
    // Collapsed state: Pointing up
    icon.innerHTML =
      '<path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd" />';
  } else {
    // Expanded state: Pointing down
    icon.innerHTML =
      '<path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />';
  }
}

function toggleSenderSelection(senderId) {
  // Handle the case where senderId might be a string or JSON object
  if (typeof senderId === "object") {
    senderId = JSON.stringify(senderId).replace(/^"|"$/g, "");
  }

  const senderCheckbox = document.getElementById(`select-sender-${senderId}`);
  if (senderCheckbox) {
    // Programmatically toggle the checkbox state
    senderCheckbox.checked = !senderCheckbox.checked;
    // Call the function that handles selecting children and updating storage
    selectAllSenderEmails(senderCheckbox, senderId);
  }
}

function selectAllSenderEmails(senderCheckbox, senderId) {
  const emailsDiv = document.getElementById(`emails-${senderId}`);
  const emailCheckboxes = emailsDiv.querySelectorAll(".email-checkbox");
  const senderGroup = document.getElementById(`sender-group-${senderId}`);
  const isChecked = senderCheckbox.checked;

  // If trying to select all and would exceed limit, show warning
  if (isChecked) {
    const selectedEmailIds = getSelectedEmailsFromStorage();
    const currentlyChecked = Array.from(emailCheckboxes).filter(
      (cb) => cb.checked
    ).length;
    const toBeAdded = Array.from(emailCheckboxes).filter(
      (cb) => !cb.checked
    ).length;

    if (selectedEmailIds.length + toBeAdded > MAX_EMAILS) {
      alert(
        `Selecting all emails from this sender would exceed the maximum limit of ${MAX_EMAILS}. Please select fewer emails.`
      );
      senderCheckbox.checked = false;
      senderCheckbox.indeterminate = currentlyChecked > 0;
      return;
    }
  }

  emailCheckboxes.forEach((cb) => {
    cb.checked = isChecked;
    const emailRow = document.getElementById(`email-${cb.value}`);
    if (emailRow) {
      emailRow.classList.toggle("email-selected", isChecked);
    }
    // Update storage for each item
    updateStorageForItem(cb.value, isChecked);
  });
  senderGroup.classList.toggle("sender-selected", isChecked);
  updateActionBar(); // Update count based on storage
}

function toggleEmailSelection(emailId) {
  // Handle the case where emailId might be a string or JSON object
  if (typeof emailId === "object") {
    emailId = JSON.stringify(emailId).replace(/^"|"$/g, "");
  }

  const emailCheckbox = document.querySelector(
    `.email-checkbox[value="${emailId}"]`
  );
  if (emailCheckbox) {
    // Check if we're trying to select (not deselect) and are at the limit
    const selectedEmailIds = getSelectedEmailsFromStorage();
    if (!emailCheckbox.checked && selectedEmailIds.length >= MAX_EMAILS) {
      alert(
        `Maximum selection limit reached (${MAX_EMAILS}). Please unselect some emails before selecting more.`
      );
      return;
    }

    emailCheckbox.checked = !emailCheckbox.checked;
    handleEmailCheckboxClick(emailCheckbox);
  }
}

function handleEmailCheckboxClick(checkbox) {
  const emailId = checkbox.value;
  const emailRow = document.getElementById(`email-${emailId}`);

  if (emailRow) {
    emailRow.classList.toggle("email-selected", checkbox.checked);
  }

  // Update storage
  updateStorageForItem(emailId, checkbox.checked);

  // Update the parent sender checkbox state
  updateSenderCheckboxState(checkbox);

  // Update action bar with count
  updateActionBar();
}

function updateSenderCheckboxState(emailCheckbox) {
  // Find the sender this email belongs to
  const sender = emailCheckbox.getAttribute("data-sender");
  if (!sender) return;

  // Convert to the same format as the ID
  const senderId = sender
    .replace(/\s+/g, "-")
    .replace(/[<>]/g, "")
    .replace(/@/g, "-")
    .replace(/\./g, "-");

  const senderCheckbox = document.getElementById(`select-sender-${senderId}`);
  if (!senderCheckbox) return;

  // Find all email checkboxes for this sender
  const emailsDiv = document.getElementById(`emails-${senderId}`);
  const allEmailCheckboxes = emailsDiv.querySelectorAll(".email-checkbox");
  const checkedEmailCheckboxes = emailsDiv.querySelectorAll(
    ".email-checkbox:checked"
  );

  // Update the sender checkbox state based on email selections
  if (checkedEmailCheckboxes.length === 0) {
    // None checked
    senderCheckbox.checked = false;
    senderCheckbox.indeterminate = false;
    document
      .getElementById(`sender-group-${senderId}`)
      .classList.remove("sender-selected");
  } else if (checkedEmailCheckboxes.length === allEmailCheckboxes.length) {
    // All checked
    senderCheckbox.checked = true;
    senderCheckbox.indeterminate = false;
    document
      .getElementById(`sender-group-${senderId}`)
      .classList.add("sender-selected");
  } else {
    // Some checked
    senderCheckbox.checked = false;
    senderCheckbox.indeterminate = true;
    document
      .getElementById(`sender-group-${senderId}`)
      .classList.add("sender-selected");
  }
}

function updateAllSenderCheckboxes() {
  // Get all sender checkboxes
  const senderCheckboxes = document.querySelectorAll(".sender-checkbox");

  // For each sender, determine the state based on its email checkboxes
  senderCheckboxes.forEach((senderCheckbox) => {
    const sender = senderCheckbox.getAttribute("data-sender");
    if (!sender) return;

    // Find all email checkboxes for this sender
    const emailCheckboxes = document.querySelectorAll(
      `.email-checkbox[data-sender="${sender}"]`
    );
    const checkedEmailCheckboxes = Array.from(emailCheckboxes).filter(
      (cb) => cb.checked
    );

    // Update the sender checkbox state
    const senderId = sender
      .replace(/\s+/g, "-")
      .replace(/[<>]/g, "")
      .replace(/@/g, "-")
      .replace(/\./g, "-");
    const senderGroup = document.getElementById(`sender-group-${senderId}`);

    if (checkedEmailCheckboxes.length === 0) {
      // None checked
      senderCheckbox.checked = false;
      senderCheckbox.indeterminate = false;
      if (senderGroup) senderGroup.classList.remove("sender-selected");
    } else if (checkedEmailCheckboxes.length === emailCheckboxes.length) {
      // All checked
      senderCheckbox.checked = true;
      senderCheckbox.indeterminate = false;
      if (senderGroup) senderGroup.classList.add("sender-selected");
    } else {
      // Some checked
      senderCheckbox.checked = false;
      senderCheckbox.indeterminate = true;
      if (senderGroup) senderGroup.classList.add("sender-selected");
    }
  });
}

function getSelectedEmails() {
  return Array.from(document.querySelectorAll(".email-checkbox:checked")).map(
    (cb) => cb.value
  );
}

// --- Bulk Actions ---
function resetSelection() {
  console.log("Resetting selection...");
  // Clear storage
  saveSelectedEmailsToStorage([]);
  saveEmailDetailsToStorage({}); // Also clear email details storage

  // Uncheck all visible checkboxes
  document.querySelectorAll(".email-checkbox:checked").forEach((cb) => {
    cb.checked = false;
  });
  document.querySelectorAll(".sender-checkbox:checked").forEach((cb) => {
    cb.checked = false;
    cb.indeterminate = false; // Reset indeterminate state
  });

  // Remove visual selection state from visible rows/groups
  document.querySelectorAll(".email-selected").forEach((row) => {
    row.classList.remove("email-selected");
  });
  document.querySelectorAll(".sender-selected").forEach((group) => {
    group.classList.remove("sender-selected");
  });

  // Update the action bar (which will now hide itself)
  updateActionBar();
}

function selectAllOnPage() {
  // Get current selected email ids
  const selectedIds = getSelectedEmailsFromStorage();

  // Get all unselected email checkboxes on the current page
  const unselectedCheckboxes = Array.from(
    document.querySelectorAll(".email-checkbox:not(:checked)")
  );

  // Check if adding all unselected emails would exceed the limit
  if (selectedIds.length + unselectedCheckboxes.length > MAX_EMAILS) {
    alert(
      `Selecting all emails would exceed the maximum limit of ${MAX_EMAILS}. Please deselect some emails first.`
    );
    return;
  }

  // Select all email checkboxes on the current page
  document.querySelectorAll(".email-checkbox").forEach((checkbox) => {
    checkbox.checked = true;
    const emailId = checkbox.value;

    // Update storage for this email
    updateStorageForItem(emailId, true);

    // Update UI
    const emailRow = document.getElementById(`email-${emailId}`);
    if (emailRow) {
      emailRow.classList.add("email-selected");
    }
  });

  // Update all sender checkboxes
  document.querySelectorAll(".sender-checkbox").forEach((checkbox) => {
    checkbox.checked = true;
    checkbox.indeterminate = false;

    // Find the sender group and mark it as selected
    const senderId = checkbox.id.replace("select-sender-", "");
    const senderGroup = document.getElementById(`sender-group-${senderId}`);
    if (senderGroup) {
      senderGroup.classList.add("sender-selected");
    }
  });

  // Update the action bar
  updateActionBar();
}

// --- Global functions exposed to window ---
window.toggleCollapse = toggleCollapse;
window.toggleSenderSelection = toggleSenderSelection;
window.selectAllSenderEmails = selectAllSenderEmails;
window.toggleEmailSelection = toggleEmailSelection;
window.handleEmailCheckboxClick = handleEmailCheckboxClick;
window.resetSelection = resetSelection;
window.selectAllOnPage = selectAllOnPage;
window.closePermissionModal = closePermissionModal;
window.showPermissionModal = showPermissionModal;
