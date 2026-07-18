"""
app/agent/agent_loop.py

This is where everything from the previous steps comes together:

  1. Build a system prompt describing the current location + graph rules.
  2. Send the conversation + tool schemas to get_llm_response() (the
     Groq -> Gemini -> OpenAI fallback router).
  3. If the LLM responds with tool call(s), execute them via
     tool_registry.execute_tool(), append the results to the conversation,
     and call the LLM again so it can produce a final natural-language
     answer grounded in those results.
  4. Return the final narration text + the (possibly updated) location
     state, so the frontend can swap backgrounds / action chips.

Note on provider fallback + tools: Groq and OpenAI both use the same
OpenAI-style tool-calling schema, so tool calls work identically on
either. Gemini's call_gemini() in this project intentionally flattens
messages to plain text (see app/llm/providers.py) for simplicity, so if
Groq AND Gemini both fail is the only path where tool-calling would be
unavailable for a turn — OpenAI is still tool-call-capable as the final
fallback.
"""

import json
import re

from app.llm.router import get_llm_response
from app.agent.graph import LOCATIONS, get_available_destinations
from app.agent.session import SessionState
from app.agent.tool_registry import TOOLS, execute_tool, parse_tool_arguments

MAX_TOOL_ITERATIONS = 4

# Safety net: some models/providers (notably our Gemini fallback, which has
# no real structured tool-calling wired up in this project — see
# call_gemini() in app/llm/providers.py) will sometimes imitate a tool call
# as literal text instead of an actual API-level tool call, e.g.:
#   <function=look_up_artifact>{"query": "Pardi Khola stream origin"}</function>
# Without this, that raw syntax would get spoken/shown to the visitor
# verbatim instead of the tool ever actually running. This regex detects
# that pattern and lets us execute it for real, exactly as if it had
# arrived as a proper tool call.
_LEAKED_TOOL_CALL_RE = re.compile(r"<function\s*=\s*(\w+)>\s*(\{.*?\})\s*</function>", re.DOTALL)


class _SyntheticFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _SyntheticToolCall:
    """Mimics the .id / .function.name / .function.arguments shape the SDKs
    give us for real tool calls, so the rest of the loop can't tell the
    difference between this and a genuine structured tool call."""

    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _SyntheticFunction(name, arguments)


def _extract_leaked_tool_calls(text: str):
    """Returns (cleaned_text, [synthetic_tool_call, ...]).
    If no leaked pseudo-calls are found, returns (text, [])."""
    matches = list(_LEAKED_TOOL_CALL_RE.finditer(text))
    if not matches:
        return text, []

    synthetic_calls = [
        _SyntheticToolCall(f"leaked_{i}", m.group(1), m.group(2))
        for i, m in enumerate(matches)
    ]
    cleaned_text = _LEAKED_TOOL_CALL_RE.sub("", text).strip()
    return cleaned_text, synthetic_calls


def _serialize_tool_call(tool_call) -> dict:
    """
    Converts a tool call - whether a real SDK response object (a Pydantic
    model from Groq/OpenAI) or one of our synthetic ones from the leaked-call
    safety net - into a plain, universally JSON-serializable dict, in the
    exact shape the chat APIs expect for an assistant message's tool_calls
    field. This matters because this dict goes back into `messages` and gets
    sent in the NEXT request to whichever provider answers next - and only
    real SDK objects know how to serialize themselves; our synthetic ones
    (and, defensively, anything else) need this explicit conversion or the
    next API call fails with a JSON serialization error.
    """
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments,
        },
    }


def build_system_prompt(session: SessionState) -> str:
    node = LOCATIONS[session.current_location]
    available = get_available_destinations(session.current_location, session.gear_rented)

    return f"""You are the voice-guide for an interactive eco-tourism experience at
Devi's Fall (Patale Chhango) and Gupteshwor Mahadev Cave in Pokhara, Nepal.

The visitor is currently at: {node.name} ({node.id})
{node.description}

Locations reachable from here right now: {', '.join(available) if available else 'none'}
Gear rented (flashlight & helmet): {session.gear_rented}

Rules:
- Speak as a warm, knowledgeable local guide. Keep responses concise (2-4 sentences)
  since they will be read aloud via text-to-speech.
- Use look_up_artifact() when the visitor asks a factual question about this location.
- Use change_location() when the visitor wants to move somewhere connected. When the
  tool result includes a "travel_route" field, weave those directions naturally into
  how you announce the move (e.g. "Let's head over — just cross the road and you're
  there.") — don't just report the new location name, tell them how you got there.
- If the visitor asks how to reach Devi's Fall itself (e.g. from Lakeside, the airport,
  or the bus park) before or independent of moving through the graph, use
  look_up_artifact() — general arrival directions are included in this location's
  knowledge base.
- If the visitor wants to enter the Deep Cave Shivalaya but hasn't rented gear,
  tell them clearly they need to rent a flashlight & helmet at the Cave Entrance
  Plaza first — do not invent a way around it.
- Use calculate_subterranean_risk() when the visitor asks if the deep cave is safe,
  or before strongly encouraging them into deep_shivalaya during monsoon-context talk.
- Never invent facts not returned by look_up_artifact — if you don't know, say so.
"""


async def run_agent_turn(session: SessionState, user_message: str) -> dict:
    messages = [{"role": "system", "content": build_system_prompt(session)}]
    messages.extend(session.history)
    messages.append({"role": "user", "content": user_message})

    session.history.append({"role": "user", "content": user_message})

    for _ in range(MAX_TOOL_ITERATIONS):
        result = await get_llm_response(messages, tools=TOOLS)

        raw_tool_calls = result.raw_tool_calls
        response_text = result.text

        # Safety net: if the provider gave no real structured tool call but
        # its text contains a leaked pseudo-call, treat it as a real one.
        if not raw_tool_calls and response_text:
            cleaned_text, synthetic_calls = _extract_leaked_tool_calls(response_text)
            if synthetic_calls:
                raw_tool_calls = synthetic_calls
                response_text = cleaned_text

        if not raw_tool_calls:
            # Final natural-language answer — done.
            session.history.append({"role": "assistant", "content": response_text})
            return {
                "response_text": response_text,
                "provider": result.provider,
                "current_location": session.current_location,
                "location_name": LOCATIONS[session.current_location].name,
                "background_asset": LOCATIONS[session.current_location].background_asset,
                "gear_rented": session.gear_rented,
                "available_destinations": get_available_destinations(
                    session.current_location, session.gear_rented
                ),
            }

        # The model wants to call one or more tools.
        messages.append(
            {
                "role": "assistant",
                "content": response_text or None,
                "tool_calls": [_serialize_tool_call(tc) for tc in raw_tool_calls],
            }
        )

        for tool_call in raw_tool_calls:
            tool_name = tool_call.function.name
            tool_args = parse_tool_arguments(tool_call.function.arguments)
            tool_result = execute_tool(tool_name, tool_args, session)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                }
            )

    # Safety valve — if the model loops without settling, return whatever we have.
    return {
        "response_text": "I'm having trouble processing that — could you rephrase?",
        "provider": "none",
        "current_location": session.current_location,
        "location_name": LOCATIONS[session.current_location].name,
        "background_asset": LOCATIONS[session.current_location].background_asset,
        "gear_rented": session.gear_rented,
        "available_destinations": get_available_destinations(
            session.current_location, session.gear_rented
        ),
    }