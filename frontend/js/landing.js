// landing.js
// Handles the transition from the welcome screen into the main
// voice-driven exploration app (built in a later step).
//
// For now this just navigates to app.html — which doesn't exist yet.
// We'll build it in Step 9 of the project (main RAG/agent frontend).
// Until then, clicking the button will 404 — that's expected.

const enterBtn = document.getElementById('enter-btn');

enterBtn.addEventListener('click', () => {
  // Brief exit animation, then hand off to the main experience.
  document.body.style.transition = 'opacity 0.5s ease';
  document.body.style.opacity = '0';

  setTimeout(() => {
    window.location.href = 'app.html';
  }, 480);
});
