/**
 * JS functionality for the scan dashboard page
 */
document.addEventListener("DOMContentLoaded", function () {
  // Add event listener to scan button if present
  const scanButton = document.getElementById("scan-button");
  if (scanButton) {
    scanButton.addEventListener("click", startScan);
  }
});

/**
 * Function to handle scan button click and show loader
 */
function startScan() {
  const skeletonList = document.getElementById("skeleton-list");
  const scanButton = document.getElementById("scan-button");

  if (skeletonList && scanButton) {
    // Disable the button and change text
    scanButton.disabled = true;
    scanButton.classList.add("is-loading", "opacity-60", "cursor-not-allowed");
    scanButton.textContent = "Scanning...";

    // Add loading animation class to skeleton
    skeletonList.classList.add("skeleton-loading");

    // Allow the form submission (link navigation) to proceed
    return true;
  }

  // Fallback if elements not found
  return true;
}
