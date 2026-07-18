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
 * Rejects if recognition errors out, or if it ends without ever
 * producing a result (silence, mumbled audio, mic permission hiccup) —
 * this used to hang forever with no feedback; now it always settles.
 */
function listenOnce() {
  return new Promise((resolve, reject) => {
    if (!isSTTSupported()) {
      reject(new Error("SpeechRecognition not supported in this browser"));
      return;
    }

    let settled = false;
    const recognition = new SpeechRecognitionAPI();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      settled = true;
      resolve(event.results[0][0].transcript);
    };

    recognition.onerror = (event) => {
      settled = true;
      reject(new Error(event.error || "Speech recognition error"));
    };

    recognition.onend = () => {
      // Fires after onresult/onerror too — only reject here if neither
      // already settled the promise, so silence/no-speech doesn't hang
      // forever with the mic button stuck lit and nothing visibly happening.
      if (!settled) {
        settled = true;
        reject(new Error("no-speech"));
      }
    };

    recognition.start();
    // expose so app.js can stop() it if the user interrupts to ask something else
    window.__activeRecognition = recognition;
  });
}

function stopListening() {
  if (window.__activeRecognition) {
    window.__activeRecognition.stop();
    window.__activeRecognition = null;
  }
}

function isSpeaking() {
  return "speechSynthesis" in window && window.speechSynthesis.speaking;
}

/**
 * Immediately stops any in-progress narration. Used when the visitor
 * interrupts with a new question mid-answer.
 */
function stopSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

/**
 * Speaks the given text aloud. Cancels any in-progress speech first so
 * responses don't queue up and overlap during a fast back-and-forth.
 * `onEnd` (optional) fires when this utterance finishes naturally —
 * used to trigger the "want me to continue your previous question?"
 * follow-up only after the new answer has actually finished playing.
 */
function speak(text, onEnd) {
  if (!("speechSynthesis" in window)) {
    if (onEnd) onEnd();
    return;
  }
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.98;
  utterance.pitch = 1.0;
  utterance.lang = "en-US";
  if (onEnd) {
    utterance.onend = onEnd;
    utterance.onerror = onEnd;
  }
  window.speechSynthesis.speak(utterance);
}