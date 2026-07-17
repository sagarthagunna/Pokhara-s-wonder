"""
app/agent/tool_registry.py

Central place listing the tool schemas we hand to the LLM, and a
dispatcher that executes the right Python function when the LLM asks
to call one. Adding a 4th tool later means: write the tool file, import
it here, add one line to TOOLS and one to execute_tool()'s if-chain.
"""

import json

from app.tools.look_up_artifact import look_up_artifact, TOOL_SCHEMA as LOOKUP_SCHEMA
from app.tools.change_location import change_location, TOOL_SCHEMA as MOVE_SCHEMA
from app.tools.calculate_subterranean_risk import (
    calculate_subterranean_risk,
    TOOL_SCHEMA as RISK_SCHEMA,
)
from app.agent.session import SessionState

# Schemas sent to the LLM so it knows what tools exist and how to call them.
TOOLS = [LOOKUP_SCHEMA, MOVE_SCHEMA, RISK_SCHEMA]


def execute_tool(name: str, arguments: dict, session: SessionState) -> dict:
    """
    Executes the requested tool by name. `session` is injected here
    (rather than passed by the LLM) for the tools that need to read/mutate
    session state (change_location) or scope a query to the current
    location (look_up_artifact) — the LLM shouldn't be trusted to supply
    session-critical values itself.
    """
    if name == "look_up_artifact":
        return look_up_artifact(
            query=arguments["query"],
            current_location=session.current_location,
        )

    if name == "change_location":
        return change_location(
            destination=arguments["destination"],
            session=session,
        )

    if name == "calculate_subterranean_risk":
        return calculate_subterranean_risk(
            humidity_pct=arguments["humidity_pct"],
            water_flow_lps=arguments["water_flow_lps"],
        )

    return {"error": f"Unknown tool '{name}'"}


def parse_tool_arguments(raw_arguments) -> dict:
    """Tool-call arguments arrive as a JSON string from the SDKs — parse safely."""
    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        return json.loads(raw_arguments)
    except (TypeError, json.JSONDecodeError):
        return {}
