/**
 * Main entry point for scan results page.
 * Imports all modules and initializes functionality.
 */

// Declare global variables needed for scan results processing
window.processedEmailIds = [];
window.totalSendersToProcess = 0;
window.currentSenderIndex = 0;

// Export global functions for direct reference from HTML
window.closeErrorMessage = function () {
  closeModal();
};
