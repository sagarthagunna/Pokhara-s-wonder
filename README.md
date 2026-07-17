# Devi's Fall & Gupteshwor Cave — Stateful Voice-Driven Exploration Guide

**Topic 2** — Geological Wonders of Pokhara (Devi's Fall & Gupteshwor Cave)
An immersive, voice-driven eco-tourism guide covering Devi's Fall (Patale Chhango)
and the Gupteshwor Mahadev Cave, built as a graph-based, RAG-grounded conversational
agent.

---

## What this is

A visitor lands on a welcome screen, then explores three connected locations by
talking (or typing) to an AI guide:

```
[Devi's Fall Overlook] <───> [Cave Entrance Plaza] <───> [Deep Cave Shivalaya]
                                                                    ▲
                                              (locked until Flashlight &
                                               Safety Helmet are rented)
```

The guide answers factual questions using retrieval-augmented generation scoped
strictly to the visitor's current location, can move the visitor between
locations, and can assess whether the deep cave is currently safe to enter based
on simulated humidity/water-flow readings.

## Architecture

```
frontend/          Plain HTML/CSS/JS. No build step.
  index.html         Welcome screen
  app.html            Main exploration app
  js/speech.js         Web Speech API wrapper (STT + TTS, both free/client-side)
  js/app.js            Session, chat, chips, background swapping
  assets/images/       State-specific SVG backgrounds (one per location)

backend/            FastAPI
  app/llm/            Provider-agnostic LLM router: Groq -> Gemini -> OpenAI fallback
  app/rag/             ChromaDB + sentence-transformers, metadata-filtered by location
  app/agent/           Location graph (state machine), session store, agent tool loop
  app/tools/           The 3 required agent tools
  app/routers/         /session/* and /chat endpoints

docker/             Dockerfiles for backend and frontend
docker-compose.yml  Orchestrates both services
```

### Why this design

- **LLM fallback chain (free-tier resilience):** `app/llm/router.py` tries Groq
  first (fast, generous free tier), then Gemini, then OpenAI. Every other part of
  the app calls one function, `get_llm_response()`, and never knows which provider
  actually answered — providers can be added, removed, or reordered in one file.
- **Metadata-filtered RAG:** all three locations' knowledge lives in a single
  ChromaDB collection, but every chunk is tagged `location: <id>` at ingestion
  time (`app/rag/ingest.py`), and every query is filtered with
  `where={"location": current_location}` (`app/rag/retriever.py`). A visitor at
  Devi's Fall can never retrieve Deep Cave Shivalaya facts, and vice versa.
- **Voice pipeline runs client-side and free:** STT (`SpeechRecognition`) and TTS
  (`speechSynthesis`) are both built into the browser — no API key, no per-request
  cost, no server round-trip for audio.
- **Gear-lock as a direct action, not a tool call:** the spec requires exactly 3
  named agent tools. Renting gear is modeled as a direct frontend action (an
  action chip hitting `POST /session/{id}/rent-gear`), mirroring how walking up to
  a real rental counter is a direct action, not something negotiated through a
  guide.

## Required tools (implemented in `app/tools/`)

| Tool | Purpose |
|---|---|
| `look_up_artifact(query)` | RAG lookup, scoped to the visitor's current location |
| `change_location(destination)` | Moves the visitor along a valid graph edge, respecting the gear lock |
| `calculate_subterranean_risk(humidity_pct, water_flow_lps)` | Scenario-specific: assesses whether the deep cave is safe to enter right now |

## Running locally (without Docker)

```bash
cd backend
pip install -r requirements.txt
cp .env.template .env
# edit .env and add at least one LLM key (free Groq key: console.groq.com/keys)
python -m app.rag.ingest        # builds the vector index (also runs automatically on first boot)
uvicorn app.main:app --reload --port 8000
```

In a second terminal:
```bash
cd frontend
python3 -m http.server 8080
```

Open `http://localhost:8080/index.html` in **Chrome or Edge** (best `SpeechRecognition`
support — Firefox/Safari fall back to the text input automatically).

## Running with Docker Compose

```bash
cp backend/.env.template backend/.env
# edit backend/.env and add at least one LLM key
docker compose up --build
```

- Frontend: http://localhost:8080/index.html
- Backend API: http://localhost:8000 (docs at http://localhost:8000/docs)

The ChromaDB index builds automatically on first backend startup (persisted in a
named Docker volume, so it isn't rebuilt on every restart).

## Getting free API keys

| Provider | Where |
|---|---|
| Groq (primary) | https://console.groq.com/keys |
| Gemini (secondary) | https://aistudio.google.com/apikey |
| OpenAI (tertiary) | https://platform.openai.com/api-keys |

You only need **one** key to run the app — the router falls through to whichever
providers you've configured.

## Known limitations

- `SpeechRecognition` (STT) has inconsistent support outside Chrome/Edge; the text
  input field is always available as a fallback.
- Session state is in-memory (a Python dict), scoped to the backend process — it
  resets on backend restart. This is a deliberate scope choice for a single-user,
  session-length demo app (see the project report for the tradeoff discussion).
- `calculate_subterranean_risk` uses simulated humidity/flow inputs rather than a
  live sensor feed, since no public real-time sensor exists for this cave.

## Project report

See `PROJECT_REPORT.md` for the full requirements-to-implementation mapping,
design rationale, and testing notes.
