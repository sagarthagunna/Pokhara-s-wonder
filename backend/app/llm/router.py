"""
app/llm/router.py

This is the piece that makes the "free-tier stack" actually reliable.

get_llm_response() tries each provider IN ORDER (Groq -> Gemini -> OpenAI).
The first one that succeeds wins. If a provider isn't configured (no API
key) or throws an error (rate limited, network hiccup, etc.), we log it
and move to the next one. Only if EVERY provider fails do we raise.

Everything downstream (the agent loop, RAG, tools) calls this ONE
function and never needs to know which provider actually responded.
That's the point of the abstraction — swap, add, or reorder providers
here without touching any other file.
"""

import logging

from app.llm.providers import call_groq, call_gemini, call_openai, LLMResult

logger = logging.getLogger("llm_router")

# Order = priority. First one that's configured AND succeeds wins.
PROVIDER_CHAIN = [
    ("groq", call_groq),
    ("gemini", call_gemini),
    ("openai", call_openai),
]


async def get_llm_response(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> LLMResult:
    errors = []

    for name, fn in PROVIDER_CHAIN:
        try:
            result = await fn(messages, tools)
            logger.info(f"LLM response served by: {name}")
            return result
        except Exception as e:
            logger.warning(f"Provider '{name}' failed: {e}")
            errors.append(f"{name}: {e}")
            continue

    raise RuntimeError(
        "All LLM providers failed or are unconfigured.\n" + "\n".join(errors)
    )
