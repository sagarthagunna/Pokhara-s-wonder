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

from app.llm.router import get_llm_response
from app.agent.graph import LOCATIONS, get_available_destinations
from app.agent.session import SessionState
from app.agent.tool_registry import TOOLS, execute_tool, parse_tool_arguments

MAX_TOOL_ITERATIONS = 4


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
- Use change_location() when the visitor wants to move somewhere connected.
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

        if not result.raw_tool_calls:
            # Final natural-language answer — done.
            session.history.append({"role": "assistant", "content": result.text})
            return {
                "response_text": result.text,
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
                "content": result.text or None,
                "tool_calls": result.raw_tool_calls,
            }
        )

        for tool_call in result.raw_tool_calls:
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
