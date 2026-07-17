"""
app/llm/providers.py

One function per provider. Each function has the SAME signature:

    async def call_x(messages: list[dict], tools: list[dict] | None) -> LLMResult

so the router (router.py) can treat them interchangeably. Each function
is responsible ONLY for talking to its own API and translating the
response into our common LLMResult shape. If a provider fails for any
reason (bad key, rate limit, network error, model deprecated), it should
raise an exception — the router decides what to do about that, not the
provider function itself.

`messages` follows the OpenAI/Groq chat format:
    [{"role": "system", "content": "..."},
     {"role": "user", "content": "..."}]

`tools` (optional) follows OpenAI-style function-calling schema. We'll
wire this up properly in the "agent tools" step — for now the providers
accept it and pass it through if the SDK supports it.
"""

from dataclasses import dataclass, field

from app.config import settings


@dataclass
class LLMResult:
    text: str
    provider: str
    raw_tool_calls: list | None = field(default=None)


# ---------------------------------------------------------------------
# Groq (primary — fast, generous free tier)
# ---------------------------------------------------------------------
async def call_groq(messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
    from groq import AsyncGroq

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    kwargs = {"model": settings.GROQ_MODEL, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = await client.chat.completions.create(**kwargs)
    choice = resp.choices[0].message
    return LLMResult(
        text=choice.content or "",
        provider="groq",
        raw_tool_calls=choice.tool_calls,
    )


# ---------------------------------------------------------------------
# Gemini (secondary)
# ---------------------------------------------------------------------
async def call_gemini(messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
    import google.generativeai as genai

    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    # Gemini doesn't use the same "system/user/assistant" list shape —
    # flatten our common message format into a single prompt string.
    # (Tool-calling via Gemini's native function-calling is a possible
    # upgrade later; for the fallback path plain text is enough.)
    prompt = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)

    resp = await model.generate_content_async(prompt)
    return LLMResult(text=resp.text, provider="gemini")


# ---------------------------------------------------------------------
# OpenAI / ChatGPT (tertiary)
# ---------------------------------------------------------------------
async def call_openai(messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
    from openai import AsyncOpenAI

    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    kwargs = {"model": settings.OPENAI_MODEL, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = await client.chat.completions.create(**kwargs)
    choice = resp.choices[0].message
    return LLMResult(
        text=choice.content or "",
        provider="openai",
        raw_tool_calls=choice.tool_calls,
    )
