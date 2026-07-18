"""
app/tools/change_location.py

Required tool #2: change_location()

Lets the agent (in response to the visitor saying things like "let's head
to the cave entrance" or "take me deeper") move the visitor through the
location graph — but only along valid edges, and respecting the gear lock
on the entrance_plaza -> deep_shivalaya edge.
"""

from app.agent.graph import LOCATIONS, is_move_allowed, get_travel_route
from app.agent.session import SessionState

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "change_location",
        "description": (
            "Move the visitor to a different connected location in the exploration "
            "graph. Valid location ids: 'devis_fall', 'entrance_plaza', 'deep_shivalaya'. "
            "The deep_shivalaya location is locked until gear has been rented at "
            "entrance_plaza — if the move is not allowed, explain why to the visitor "
            "instead of pretending it happened."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "enum": ["devis_fall", "entrance_plaza", "deep_shivalaya"],
                    "description": "The location id to move to.",
                }
            },
            "required": ["destination"],
        },
    },
}


def change_location(destination: str, session: SessionState) -> dict:
    origin = session.current_location  # captured BEFORE mutating, so the route lookup uses the real edge

    allowed, reason = is_move_allowed(
        from_location=origin,
        to_location=destination,
        gear_rented=session.gear_rented,
    )

    if not allowed:
        return {"success": False, "reason": reason, "current_location": origin}

    session.current_location = destination
    node = LOCATIONS[destination]
    route = get_travel_route(origin, destination)

    return {
        "success": True,
        "current_location": destination,
        "location_name": node.name,
        "description": node.description,
        "background_asset": node.background_asset,
        "travel_route": route,
    }