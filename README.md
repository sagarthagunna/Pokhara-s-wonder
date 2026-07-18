# Pokhara's Wonder — Devi's Fall & Gupteshwor Cave: Stateful Voice-Driven Exploration Guide

## Selected Scenario

**Topic 2 — Geological Wonders of Pokhara (Devi's Fall & Gupteshwor Cave)**, from the
Library of 18 Immersive Tourism, Heritage, and Exploration Scenarios.

The user is an eco-tourist exploring the powerful geological water drop at Devi's Fall
(Patale Chhango) and following the subterranean channel down into the deep Gupteshwor
Mahadev Cave.

---

## Prerequisites

| Requirement | Version / Notes |
|---|---|
| Docker | 24.x or later, with Docker Compose v2 (`docker compose`, not the standalone `docker-compose`) |
| Docker Desktop | Required on Windows/Mac — must be running before any `docker compose` command. On Windows, Docker Desktop uses WSL2 internally; no manual WSL setup is needed beyond keeping it updated (`wsl --update`) |
| Git | 2.x or later, only needed if cloning rather than downloading the zip |
| A modern browser | **Chrome or Edge strongly recommended** — the voice input (`SpeechRecognition`) has limited or no support in Firefox/Safari. The app falls back to a text input automatically either way |
| At least one free LLM API key | Groq (recommended, fastest), Gemini, and/or OpenAI — see [Getting free API keys](#getting-free-api-keys) below. Only one is strictly required; the rest are optional fallbacks |
| ~2 GB free disk space | For Docker images plus the one-time embedding model download (~90 MB, cached after first run) |

No local Python or Node.js installation is required — everything runs inside containers.

---

## Setup Instructions

### 1. Prepare your environment file

```bash
cp backend/.env.template backend/.env
```

Open `backend/.env` and paste in at least one API key:

```dotenv
GROQ_API_KEY=gsk_your_key_here
```

> ⚠️ **Never commit or submit `backend/.env` itself** — only `.env.template` (with no
> real values) should ever be shared or version-controlled. Treat any key that's been
> pasted somewhere outside your local `.env` (chat, ticket, screenshot) as compromised
> and rotate it immediately.

### 2. Build and start the containers

```bash
docker compose up --build
```

This builds two images (backend, frontend) and starts both. On first boot, the backend
automatically downloads the sentence-embedding model and builds the RAG vector index —
this takes a minute or two the very first time only, then is cached in a Docker volume.

### 3. Open the app

- **Frontend (start here):** [http://localhost:8080/index.html](http://localhost:8080/index.html)
- **Backend API / docs:** [http://localhost:8001](http://localhost:8001) (interactive docs at `http://localhost:8001/docs`)

> **Port note:** the backend is published on host port `8001` (not `8000`) in this
> project's `docker-compose.yml`, to avoid a common conflict with other local services
> that default to `8000`. If you change this, also update `API_BASE` in
> `frontend/js/config.js` to match, then rebuild.

### 4. Verify it's working

```bash
curl http://localhost:8001/health
```

You should see `"status": "ok"` and `true` next to whichever provider key(s) you set.

### Stopping / resetting

```bash
docker compose down          # stop containers, keep the RAG index cached
docker compose down -v       # stop AND wipe the RAG index volume (forces a clean
                              # re-embed next startup - needed if you edit the
                              # knowledge .txt files under backend/app/rag/knowledge/)
```

---

## Architecture: How State Transitions Are Maintained and Validated

### The navigation graph

```
   [Devi's Fall Overlook]  <──────────>  [Cave Entrance Plaza]  <──────────>  [Deep Cave Shivalaya]
                                                                    ▲                    ▲
                                                                    └── locked until ─────┘
                                                                        Flashlight & Helmet
                                                                        are rented
```

This is modeled as a plain adjacency structure in `backend/app/agent/graph.py` —
deliberately dependency-free (no graph library) so the state logic is easy to read
and reason about:

- **`LocationNode`** — a dataclass holding each location's id, name, description,
  background image, and the list of location ids it connects to (`connects_to`).
- **`is_move_allowed(from, to, gear_rented)`** — the single gatekeeper function that
  validates every proposed move. It checks (1) whether the edge exists in the graph at
  all, and (2) whether the one conditional edge (`entrance_plaza → deep_shivalaya`)
  is unlocked. It returns a clear rejection reason string when a move isn't allowed,
  rather than silently failing.
- **`get_available_destinations(current_location, gear_rented)`** — computes the live
  list of reachable locations for the *current* state, used to drive which movement
  chips the frontend shows as enabled vs. locked.

### Where state actually lives

State is held in a simple in-memory session object (`app/agent/session.py`):

```python
SessionState:
    session_id: str
    current_location: str   # one of the 3 location ids
    gear_rented: bool       # the one persistent flag gating the locked edge
    history: list[dict]     # conversation turns, for LLM context
```

A dict keyed by `session_id` holds all active sessions. This is a deliberate scope
choice for a single-user, session-length (~1 hour) interactive experience as specified
in the assignment — not a multi-user, cross-restart product. The single
`get_session()` / `create_session()` interface means swapping in a persistent store
(e.g. Redis) later would only require changing this one file.

### How a transition actually happens

1. The visitor says (or types) something like "take me to the cave entrance."
2. The LLM agent loop (`app/agent/agent_loop.py`) recognizes this as a location-change
   intent and calls the **`change_location`** tool.
3. `app/tools/change_location.py` captures the *origin* location, calls
   `is_move_allowed()`, and only mutates `session.current_location` if the move
   validates. If the move is locked, the session state is left untouched and a
   human-readable reason is returned instead.
4. On a successful move, the tool also attaches a `travel_route` string (from a
   `TRAVEL_ROUTES` lookup table keyed by `(origin, destination)`) describing how to
   physically get there — the agent weaves this into its spoken response rather than
   just announcing the new location name.
5. The updated location, background asset, gear status, and newly-available
   destinations are returned to the frontend, which swaps the background image and
   re-renders the context-aware action chips accordingly.

### The one locking condition

The `entrance_plaza → deep_shivalaya` edge additionally requires `session.gear_rented
== True`. Renting gear is deliberately implemented as a direct state-mutating REST
action (`POST /session/{id}/rent-gear`, only accepted while standing at
`entrance_plaza`) rather than a 4th LLM tool — since the assignment specifies exactly
three named tools, and renting equipment from a counter is a direct real-world action,
not something negotiated conversationally.

---

## Required Tools

| Tool | File | Purpose |
|---|---|---|
| `look_up_artifact(query)` | `app/tools/look_up_artifact.py` | Metadata-filtered RAG lookup, scoped strictly to the visitor's current location |
| `change_location(destination)` | `app/tools/change_location.py` | Validates and executes moves through the graph, respecting the gear lock |
| `calculate_subterranean_risk(humidity_pct, water_flow_lps)` | `app/tools/calculate_subterranean_risk.py` | Scenario-specific: assesses whether the Deep Cave Shivalaya is currently safe to enter |

## Metadata-Filtered RAG

All three locations' knowledge lives in a single ChromaDB collection
(`app/rag/ingest.py`), but every chunk is tagged with a `location` metadata field at
ingestion time. Every retrieval call filters with `where={"location": current_location}`
(`app/rag/retriever.py`), so a visitor standing at Devi's Fall can never retrieve Deep
Cave Shivalaya facts, and vice versa — verified directly during development with zero
cross-location leakage in testing.

## LLM Provider Fallback Chain

`app/llm/router.py` tries **Groq → Gemini → OpenAI**, in that order, returning the
first successful response. Every other part of the app calls one function,
`get_llm_response()`, and never knows which provider actually answered — providers can
be added, removed, or reordered in one file. A safety net in `app/agent/agent_loop.py`
also catches and correctly executes tool calls that a non-tool-calling fallback model
attempts to "fake" as literal text, rather than showing that raw text to the visitor.

## Voice Pipeline (STT → LLM → TTS)

Both speech-to-text and text-to-speech run **client-side and free**, via the browser's
built-in Web Speech API (`frontend/js/speech.js`) — no API key, no per-request cost, no
audio upload round-trip. The app also supports **mid-answer interruption**: asking a
new question while the guide is still talking immediately stops the old narration,
cancels the in-flight request for it, answers the new question, and then offers to
resume the interrupted one once the new answer finishes playing.

## Frontend

Plain HTML/CSS/JS, no build step. `frontend/app.html` provides state-specific
background photography per location, a narration panel, and context-aware action
chips (movement chips respecting the gear lock, a gear-rental chip only shown where
relevant, and per-location suggested questions).

---

## Getting Free API Keys

| Provider | Where | Notes |
|---|---|---|
| Groq (primary) | https://console.groq.com/keys | Free tier: no credit card, ~30 req/min, ~1,000 req/day. Fastest inference |
| Gemini (secondary) | https://aistudio.google.com/apikey | Free tier: no credit card. Use model `gemini-2.5-flash` — older `gemini-1.5-flash`/`gemini-2.0-flash` have been shut down |
| OpenAI (tertiary) | https://platform.openai.com/api-keys | **Not actually free** — requires a funded account even for light use. Optional; the app works fine on Groq + Gemini alone |

You only need **one** key configured for the app to work — the fallback chain uses
whichever providers you've set.

## Known Limitations

- `SpeechRecognition` (STT) has inconsistent browser support outside Chrome/Edge; the
  text input field is always available as a fallback.
- Session state is in-memory, scoped to the backend process — it resets on backend
  restart. Deliberate scope choice for a single-user, session-length demo app.
- `calculate_subterranean_risk` uses simulated humidity/flow inputs rather than a live
  sensor feed, since no public real-time sensor exists for this cave.
- The OpenAI fallback requires a funded API account and will not work on a truly free
  setup — Groq and Gemini alone cover the fallback chain's practical needs.

## Project Report

See `PROJECT_REPORT.md` for the full requirements-to-implementation mapping, design
rationale, sourcing notes for the knowledge base content, and the testing log.