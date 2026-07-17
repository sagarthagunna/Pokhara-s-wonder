// js/speech.js
//
// Wraps the browser's built-in Web Speech API for both halves of the
// voice pipeline:
//   - SpeechRecognition  -> Speech-to-Text (STT)
//   - speechSynthesis    -> Text-to-Speech (TTS)
//
// Both are free, run entirely client-side (no API key, no server round
// trip), and ship in Chrome/Edge by default. Firefox/Safari support for
// SpeechRecognition is limited or absent — the app falls back to the
// text input field automatically when it's unavailable (see app.js).

const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

function isSTTSupported() {
  return !!SpeechRecognitionAPI;
}

/**
 * Starts listening once and resolves with the transcript.
 * Rejects if recognition errors out or the user doesn't say anything.
 */
function listenOnce() {
  return new Promise((resolve, reject) => {
    if (!isSTTSupported()) {
      reject(new Error("SpeechRecognition not supported in this browser"));
      return;
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      resolve(transcript);
    };

    recognition.onerror = (event) => {
      reject(new Error(event.error || "Speech recognition error"));
    };

    recognition.onend = () => {
      // If onresult never fired (silence/timeout), onend fires with nothing
      // resolved yet — reject so the UI can reset instead of hanging.
    };

    recognition.start();
    // expose so app.js can stop() it if the user cancels
    window.__activeRecognition = recognition;
  });
}

function stopListening() {
  if (window.__activeRecognition) {
    window.__activeRecognition.stop();
    window.__activeRecognition = null;
  }
}

/**
 * Speaks the given text aloud. Cancels any in-progress speech first so
 * responses don't queue up and overlap during a fast back-and-forth.
 */
function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.98;
  utterance.pitch = 1.0;
  utterance.lang = "en-US";
  window.speechSynthesis.speak(utterance);
}
