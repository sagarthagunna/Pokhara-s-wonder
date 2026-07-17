# Project Report

## Devi's Fall & Gupteshwor Cave — Stateful Voice-Driven Interactive Exploration Guide

**Assigned Topic:** Topic 2 — Geological Wonders of Pokhara (Devi's Fall & Gupteshwor Cave)

---

## 1. Premise recap

The user is modeled as an eco-tourist standing at Devi's Fall (Patale Chhango),
where the Pardi Khola river vanishes into a limestone sinkhole, then following that
same water underground into the Gupteshwor Mahadev Cave — first through the surface
Cave Entrance Plaza, then, once properly equipped, into the Deep Cave Shivalaya.

## 2. Requirement-by-requirement implementation mapping

| Requirement | Implementation |
|---|---|
| Graph-based state machine, ≥3 connected locations | `backend/app/agent/graph.py` — `LOCATIONS` dict of `LocationNode`s with explicit `connects_to` edges; `devis_fall <-> entrance_plaza <-> deep_shivalaya` |
| Metadata-filtered RAG (ChromaDB) | `backend/app/rag/ingest.py` tags every chunk with `location` metadata at ingestion; `backend/app/rag/retriever.py` queries with `where={"location": ...}` |
| `look_up_artifact()` tool | `backend/app/tools/look_up_artifact.py` — wraps the retriever, scoped to the visitor's current location |
| `change_location()` tool | `backend/app/tools/change_location.py` — validates against the graph edges and the gear lock before mutating session state |
| Scenario-specific custom tool | `backend/app/tools/calculate_subterranean_risk.py` — `calculate_subterranean_risk(humidity_pct, water_flow_lps)` |
| STT → LLM → TTS pipeline | STT/TTS: browser Web Speech API (`frontend/js/speech.js`, client-side, free). LLM: `backend/app/llm/router.py` fallback chain (Groq → Gemini → OpenAI) |
| State-specific background images | `frontend/assets/images/{location}.svg`, swapped in `frontend/js/app.js` on location change |
| Narration panel | `#narration-panel` in `app.html`, populated by `addMessage()` in `app.js` |
| Context-aware action chips | `renderChips()` in `app.js` — movement chips (respecting the gear lock), a gear-rental chip (only at the plaza, only until rented), and per-location suggested-question chips |
| Docker Compose containerization | `docker-compose.yml`, `docker/Dockerfile.backend`, `docker/Dockerfile.frontend` |
| Prescribed directory structure + deliverables | See repository tree in `README.md`; includes backend, frontend, Docker config, `README.md`, `backend/.env.template`, this report |
| State-locking condition | `is_move_allowed()` in `graph.py` rejects `entrance_plaza -> deep_shivalaya` unless `session.gear_rented is True`; gear is rented via `POST /session/{id}/rent-gear`, only accepted while standing at `entrance_plaza` |

## 3. Architecture decisions and rationale

### 3.1 Free-tier-first LLM strategy
Per project constraints, the entire stack avoids paid dependencies wherever a free
tier or client-side alternative exists. The one architectural risk of relying on
free-tier LLM APIs is rate limiting during a sustained ~1 hour session. This is
addressed with a **provider fallback chain** (`app/llm/router.py`): Groq is tried
first for its speed and generous free tier; if it fails for any reason (rate limit,
timeout, missing key), the router falls through to Gemini, then OpenAI, without any
other part of the application needing to know which provider ultimately answered.
This is a standard resilience pattern (comparable to a circuit breaker with ordered
fallbacks) applied to LLM provider selection specifically.

### 3.2 Metadata-filtered RAG as a hard boundary, not a soft one
The spec's "RAG Boundaries" section implies each location should only be able to
surface its own facts. Rather than relying on prompt instructions alone (which an
LLM can drift from), the boundary is enforced at the retrieval layer: all three
locations' source documents are embedded into a single ChromaDB collection, but every
chunk carries a `location` metadata field set at ingestion time, and every retrieval
call passes `where={"location": current_location}`. This means even if the LLM
"wanted" to answer with Deep Cave facts while the visitor is at Devi's Fall, the tool
call itself cannot return chunks outside that filter — a boundary the LLM cannot argue
its way around. This was verified directly (see Section 5, Test 1).

### 3.3 Client-side STT/TTS
Rather than a server-side pipeline (e.g. Whisper API + a TTS API), both halves of the
voice pipeline run in the browser via the Web Speech API. This keeps the entire voice
loop free and removes an audio-upload round trip, at the cost of `SpeechRecognition`
browser support being inconsistent outside Chromium-based browsers — documented as a
known limitation, with a text-input fallback always available.

### 3.4 Session state as an in-memory store
Given the assignment's single-user, session-scoped framing (~1 hour interactive
session, not a persistent multi-user product), session state is kept in a simple
in-memory Python dict (`app/agent/session.py`) rather than a database. This was a
deliberate scope decision: it is fully sufficient for the assignment's stated use
case, and the single `get_session()`/`create_session()` interface means swapping in
a persistent store (e.g. Redis) later would require changing only that one file.

### 3.5 Gear rental as a direct action, not a 4th tool
The spec enumerates exactly three required tools. Rather than inventing a fourth tool
for gear rental, it's modeled as a direct state-mutating REST action
(`POST /session/{id}/rent-gear`), exposed to the user as an action chip rather than
something negotiated conversationally through the LLM. This mirrors the real-world
action it represents (walking to a counter and renting equipment is not a
conversation) and keeps the tool count exactly as specified.

## 4. Data sourcing

The RAG knowledge base (`backend/app/rag/knowledge/*.txt`) was compiled from public
tourism and geological reference sources on Devi's Fall and Gupteshwor Mahadev Cave,
including sinkhole depth estimates, the 1961 naming legend, cave length surveys
(reported between ~2,057 m and ~2,950 m depending on source, both figures included
with attribution to that variance), ticket pricing, and the cave's 16th-century
discovery legend alongside its 1991 constructed-entrance date. Where sources
disagreed (e.g. exact cave length, exact discovery date), the discrepancy itself is
noted in the knowledge text rather than silently picking one figure, since this is
a documented characteristic of an actively-surveyed wet karst cave system.

## 5. Testing performed

All of the following were run against the actual implementation during development
(not just reasoned about):

1. **RAG metadata filtering boundary** — indexed all three locations' documents into
   one collection, then queried with `where={"location": "entrance_plaza"}` and
   confirmed 100% of returned chunks were tagged `entrance_plaza`, with zero leakage
   from the other two locations. Repeated for `deep_shivalaya`.
2. **Graph state machine** — verified `devis_fall` only connects to `entrance_plaza`;
   verified `deep_shivalaya` is excluded from `entrance_plaza`'s available
   destinations when `gear_rented=False` and included when `True`; verified
   `is_move_allowed()` returns a clear, correct rejection reason for the locked edge.
3. **calculate_subterranean_risk** — tested across dry-season (low humidity/flow →
   `safe`), shoulder-season (moderate → `caution`), and monsoon-level (high → `unsafe`)
   input scenarios, plus out-of-range input clamping (negative flow, >100% humidity).
4. **Agent tool-calling loop** — tested `run_agent_turn()` end-to-end with a mocked
   LLM response simulating a `change_location` tool call, confirming the tool executes,
   session state updates, and a grounded final response is returned.
5. **API layer** — booted the FastAPI app, confirmed `/health`, `/session/new`,
   `/session/{id}/state`, and `/session/{id}/rent-gear` all respond correctly,
   including the 400 rejection when attempting to rent gear from the wrong location.
6. **Frontend JS** — all four JavaScript files pass `node --check` with no syntax
   errors.

Not testable in the development sandbox (network-restricted, no outbound access to
LLM provider APIs or the HuggingFace model hub): a live end-to-end call through a
real Groq/Gemini/OpenAI key, and the first-run embedding-model download. Both are
expected to work identically on a machine with normal internet access, and the
ingestion/router logic itself was verified in isolation per items 1 and 4 above.

## 6. Known limitations

- `SpeechRecognition` browser support is inconsistent outside Chromium browsers.
- Session state does not persist across backend restarts (in-memory, by design).
- The risk tool's thresholds (humidity/flow bands) are reasonable domain assumptions
  documented in code comments, not measured field data from an installed sensor.
