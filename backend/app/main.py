"""
app/main.py

Entry point. Run locally with:
    uvicorn app.main:app --reload --port 8000

Right now this exposes just two endpoints so we can verify the
foundation works before building anything on top of it:

  GET  /health        -> confirms the server is alive
  POST /llm/test       -> sends a message through the provider fallback
                          chain and tells you which provider answered

Everything else (location graph, RAG, tools, chat pipeline) gets added
in later steps as routers/ files and included below.
"""

import logging
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.llm.router import get_llm_response
from app.routers import session as session_router
from app.routers import chat as chat_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="Devi's Fall & Gupteshwor Cave Explorer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router.router)
app.include_router(chat_router.router)


@app.on_event("startup")
async def build_rag_index_if_missing():
    """
    Auto-builds the ChromaDB index on first boot so `docker compose up`
    just works without a manual ingestion step. Safe to call repeatedly -
    ingest.build_index() rebuilds from scratch each time it runs.

    Runs in a thread executor (not directly awaited) because building the
    index is CPU/network-bound sync code (downloading the embedding model
    on first run, then embedding all chunks) - running it directly in the
    startup coroutine would block the whole event loop, including /health,
    until it finished. Wrapped in try/except so a slow or unreachable
    embedding-model download (e.g. restricted network) degrades gracefully
    to a log warning instead of crashing server startup - the app still
    boots and you can run `python -m app.rag.ingest` manually once network
    access is available.
    """
    import asyncio

    persist_dir = pathlib.Path(settings.CHROMA_PERSIST_DIR)
    index_exists = persist_dir.exists() and any(persist_dir.iterdir())

    if index_exists:
        logger.info("Existing RAG index found - skipping rebuild.")
        return

    logger.info("No existing RAG index found - building it in the background...")

    def _build():
        try:
            from app.rag.ingest import build_index
            build_index()
            logger.info("RAG index build complete.")
        except Exception as e:
            logger.warning(
                f"RAG index build failed ({e}). The app will still start, but "
                "look_up_artifact will return no results until you run "
                "`python -m app.rag.ingest` successfully."
            )

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _build)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "providers_configured": {
            "groq": bool(settings.GROQ_API_KEY),
            "gemini": bool(settings.GEMINI_API_KEY),
            "openai": bool(settings.OPENAI_API_KEY),
        },
    }


class LLMTestRequest(BaseModel):
    message: str


@app.post("/llm/test")
async def llm_test(payload: LLMTestRequest):
    """
    Manual sanity check for the fallback chain. Send any message and
    see which provider answers. Useful for confirming your .env keys
    are actually working before building the full agent on top of it.
    """
    messages = [
        {"role": "system", "content": "You are a concise assistant. Reply in one sentence."},
        {"role": "user", "content": payload.message},
    ]
    result = await get_llm_response(messages)
    return {"provider_used": result.provider, "response": result.text}
