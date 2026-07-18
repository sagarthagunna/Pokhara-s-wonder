// js/app.js
//
// Ties together: session lifecycle, the narration panel, context-aware
// action chips, background swapping, and the STT -> backend -> TTS loop.

const locationNameEl = document.getElementById("location-name");
const statusPill = document.getElementById("status-pill");
const backgroundEl = document.getElementById("background");
const narrationPanel = document.getElementById("narration-panel");
const narrationEmpty = document.getElementById("narration-empty");
const chipsRow = document.getElementById("chips-row");
const micBtn = document.getElementById("mic-btn");
const textForm = document.getElementById("text-form");
const textInput = document.getElementById("text-input");

let sessionId = null;
let currentState = null; // last known { current_location, background_asset, gear_rented, available_destinations }

// --- Interrupt-and-resume state ---
// currentAbortController: cancels the in-flight /chat request for whatever
//   question is currently being answered, if the visitor interrupts with a
//   new one before it finishes.
// currentlyAnsweringQuestion: the question text tied to that in-flight
//   request / currently-playing narration.
// interruptedQuestion: set when an interruption happens, so we can offer to
//   come back to it once the new question has been answered.
let currentAbortController = null;
let currentlyAnsweringQuestion = null;
let interruptedQuestion = null;

// Friendly display names + suggested questions per location, used to
// build context-aware action chips (the spec's third frontend requirement).
const LOCATION_META = {
  devis_fall: {
    label: "Devi's Fall Overlook",
    suggestions: [
      "How deep is the sinkhole?",
      "Where does this water come from?",
      "How did Devi's Fall get its name?",
    ],
  },
  entrance_plaza: {
    label: "Cave Entrance Plaza",
    suggestions: [
      "How much is the entrance ticket?",
      "How long is the cave?",
      "When was the cave discovered?",
    ],
  },
  deep_shivalaya: {
    label: "Deep Cave Shivalaya",
    suggestions: [
      "Is it safe to be down here right now?",
      "Tell me about the stalactites.",
      "What's making that water sound?",
    ],
  },
};

function setStatus(text, kind) {
  statusPill.textContent = text;
  statusPill.className = "status-pill " + (kind || "");
}

function setBackground(assetFilename) {
  backgroundEl.classList.add("fading");
  setTimeout(() => {
    backgroundEl.style.backgroundImage = `url('assets/images/${assetFilename}')`;
    backgroundEl.classList.remove("fading");
  }, 250);
}

function addMessage(role, text) {
  narrationEmpty.style.display = "none";
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  narrationPanel.appendChild(div);
  narrationPanel.scrollTop = narrationPanel.scrollHeight;
}

function renderChips(state) {
  chipsRow.innerHTML = "";
  const meta = LOCATION_META[state.current_location];

  // Movement chips - one per reachable location
  const allLocations = ["devis_fall", "entrance_plaza", "deep_shivalaya"];
  for (const loc of allLocations) {
    if (loc === state.current_location) continue;
    const reachable = state.available_destinations.includes(loc);
    const locked = loc === "deep_shivalaya" && !state.gear_rented && !reachable;

    const chip = document.createElement("button");
    chip.className = "chip chip-move" + (locked ? " chip-locked" : "");
    chip.textContent = locked ? `🔒 ${LOCATION_META[loc].label}` : `→ ${LOCATION_META[loc].label}`;
    if (reachable) {
      chip.addEventListener("click", () => sendMessage(`Take me to ${LOCATION_META[loc].label}`));
    } else if (locked) {
      chip.addEventListener("click", () =>
        addMessage("system", "Locked — rent a Flashlight & Safety Helmet at the Cave Entrance Plaza first.")
      );
    }
    chipsRow.appendChild(chip);
  }

  // Gear rental chip - only shown at entrance_plaza, only while not yet rented
  if (state.current_location === "entrance_plaza" && !state.gear_rented) {
    const chip = document.createElement("button");
    chip.className = "chip chip-gear";
    chip.textContent = "🔦 Rent Flashlight & Helmet";
    chip.addEventListener("click", rentGear);
    chipsRow.appendChild(chip);
  }

  // Suggested question chips, specific to the current location
  for (const q of meta.suggestions) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = q;
    chip.addEventListener("click", () => sendMessage(q));
    chipsRow.appendChild(chip);
  }
}

function applyState(state) {
  const prevLocation = currentState ? currentState.current_location : null;
  currentState = state;

  locationNameEl.textContent = LOCATION_META[state.current_location].label;
  if (state.current_location !== prevLocation) {
    setBackground(state.background_asset);
  }
  renderChips(state);
}

async function startSession() {
  setStatus("connecting…");
  try {
    const res = await fetch(`${API_BASE}/session/new`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to create session");
    const data = await res.json();
    sessionId = data.session_id;
    applyState(data);
    setStatus("connected", "ok");
    addMessage("guide", data.description);
  } catch (err) {
    console.error(err);
    setStatus("offline — backend unreachable", "error");
    addMessage(
      "system",
      "Couldn't reach the backend. Make sure it's running (see README) and reachable at " + API_BASE
    );
  }
}

async function sendMessage(text) {
  if (!sessionId || !text.trim()) return;

  // --- Interrupt handling ---
  // If the guide is still speaking, or a previous /chat request is still
  // in flight, this new message counts as an interruption: stop the old
  // narration immediately, abort the old network request so its answer
  // can't "catch up" and get spoken later on top of the new one, and
  // remember what was interrupted so we can offer to resume it afterward.
  const wasInterrupting = isSpeaking() || currentAbortController !== null;
  if (wasInterrupting) {
    stopSpeaking();
    if (currentAbortController) {
      currentAbortController.abort();
    }
    if (currentlyAnsweringQuestion) {
      interruptedQuestion = currentlyAnsweringQuestion;
    }
  }

  addMessage("visitor", text);
  currentlyAnsweringQuestion = text;

  const abortController = new AbortController();
  currentAbortController = abortController;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
      signal: abortController.signal,
    });
    if (!res.ok) throw new Error("Chat request failed");
    const data = await res.json();

    addMessage("guide", data.response_text);
    applyState(data);

    // Only offer to resume the old question once the NEW answer has
    // actually finished playing aloud — not before, so the two answers
    // never overlap or compete for attention.
    const questionToResume = interruptedQuestion;
    interruptedQuestion = null;
    speak(data.response_text, () => {
      if (questionToResume) offerResume(questionToResume);
    });
  } catch (err) {
    if (err.name === "AbortError") {
      // Expected when the visitor interrupted this exact request — the
      // new question's request is already handling the response, so
      // there's nothing to show the user here.
      return;
    }
    console.error(err);
    addMessage("system", "Something went wrong reaching the guide. Please try again.");
  } finally {
    if (currentAbortController === abortController) {
      currentAbortController = null;
      currentlyAnsweringQuestion = null;
    }
  }
}

function offerResume(question) {
  addMessage("system", `We got sidetracked — want me to go back to "${question}"?`);

  const chip = document.createElement("button");
  chip.className = "chip chip-resume";
  const short = question.length > 44 ? question.slice(0, 44) + "…" : question;
  chip.textContent = `↩ Continue: "${short}"`;
  chip.addEventListener("click", () => {
    chip.remove();
    sendMessage(question);
  });
  chipsRow.prepend(chip);
}

async function rentGear() {
  if (!sessionId) return;
  try {
    const res = await fetch(`${API_BASE}/session/${sessionId}/rent-gear`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      addMessage("system", data.detail || "Could not rent gear right now.");
      return;
    }
    addMessage("system", data.message);
    speak(data.message);
    // Refresh full state so chips/backgrounds reflect gear_rented=true
    const stateRes = await fetch(`${API_BASE}/session/${sessionId}/state`);
    applyState(await stateRes.json());
  } catch (err) {
    console.error(err);
    addMessage("system", "Could not reach the gear vendor right now.");
  }
}

// --- Input wiring ---

textForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = textInput.value;
  textInput.value = "";
  sendMessage(text);
});

let listening = false;
micBtn.addEventListener("click", async () => {
  if (!isSTTSupported()) {
    addMessage(
      "system",
      "Voice input isn't supported in this browser. Try Chrome or Edge, or type your question below."
    );
    return;
  }

  if (listening) {
    stopListening();
    listening = false;
    micBtn.classList.remove("listening");
    return;
  }

  // Tapping the mic while the guide is talking is itself an interruption —
  // stop the narration right away so it isn't still playing while you speak.
  if (isSpeaking()) {
    stopSpeaking();
  }

  listening = true;
  micBtn.classList.add("listening");
  try {
    const transcript = await listenOnce();
    await sendMessage(transcript);
  } catch (err) {
    if (err.message === "no-speech") {
      addMessage("system", "Didn't catch that — try again, or type your question below.");
    } else {
      console.warn("Speech recognition:", err.message);
      addMessage("system", "Voice input had a problem. Try again, or type your question below.");
    }
  } finally {
    listening = false;
    micBtn.classList.remove("listening");
  }
});

startSession();