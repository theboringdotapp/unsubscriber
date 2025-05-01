/**
 * Theme toggle functionality for light/dark mode
 */
document.addEventListener("DOMContentLoaded", function () {
  const themeToggle = document.getElementById("theme-toggle");
  const sunIcon = document.querySelector(".sun-icon");
  const moonIcon = document.querySelector(".moon-icon");

  // Set initial icon state
  function initializeTheme() {
    if (document.documentElement.classList.contains("dark")) {
      sunIcon.style.display = "block";
      moonIcon.style.display = "none";
    } else {
      sunIcon.style.display = "none";
      moonIcon.style.display = "block";
    }
  }

  // Toggle theme when button is clicked
  function setupThemeToggle() {
    if (!themeToggle) return;

    themeToggle.addEventListener("click", function () {
      document.documentElement.classList.toggle("dark");

      if (document.documentElement.classList.contains("dark")) {
        localStorage.theme = "dark";
        sunIcon.style.display = "block";
        moonIcon.style.display = "none";
      } else {
        localStorage.theme = "light";
        sunIcon.style.display = "none";
        moonIcon.style.display = "block";
      }
    });
  }

  initializeTheme();
  setupThemeToggle();
});
