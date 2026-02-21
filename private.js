/*
  PASSWORD GATE
  This is a courtesy lock, not real security.
*/

// CHANGE THIS PASSWORD
const PASSWORD = "change-this-password";

// RUN ON PAGE LOAD
document.addEventListener("DOMContentLoaded", () => {

  const attempt = prompt("Enter password:");

  // WRONG PASSWORD OR CANCEL
  if (attempt !== PASSWORD) {
    // REDIRECT BACK TO HOME
    window.location.href = "index.html";
    return;
  }

  // CORRECT PASSWORD
  document.getElementById("privateContent").style.display = "block";
});
