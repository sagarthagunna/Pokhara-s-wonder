"""
app/routers/session.py

Endpoints for session lifecycle and the gear-rental action.

Gear rental is deliberately a plain state-mutating endpoint rather than
an LLM tool call — the spec requires exactly the 3 named tools
(look_up_artifact, change_location, calculate_subterranean_risk), so the
"rent gear" action is modeled as a direct frontend action (an action chip
button), the same way clicking a real gear-vendor counter would be a
direct action, not something you'd negotiate with the guide over.
"""

from fastapi import APIRouter, HTTPException

from app.agent.session import create_session, get_session
from app.agent.graph import LOCATIONS, get_available_destinations

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/new")
async def new_session():
    session = create_session()
    node = LOCATIONS[session.current_location]
    return {
        "session_id": session.session_id,
        "current_location": session.current_location,
        "location_name": node.name,
        "description": node.description,
        "background_asset": node.background_asset,
        "gear_rented": session.gear_rented,
        "available_destinations": get_available_destinations(
            session.current_location, session.gear_rented
        ),
    }


@router.get("/{session_id}/state")
async def get_state(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    node = LOCATIONS[session.current_location]
    return {
        "session_id": session.session_id,
        "current_location": session.current_location,
        "location_name": node.name,
        "description": node.description,
        "background_asset": node.background_asset,
        "gear_rented": session.gear_rented,
        "available_destinations": get_available_destinations(
            session.current_location, session.gear_rented
        ),
    }


@router.post("/{session_id}/rent-gear")
async def rent_gear(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.current_location != "entrance_plaza":
        raise HTTPException(
            status_code=400,
            detail="Gear can only be rented at the Cave Entrance Plaza.",
        )

    session.gear_rented = True
    return {
        "gear_rented": True,
        "message": "Flashlight & Safety Helmet rented. The Deep Cave Shivalaya is now accessible.",
        "available_destinations": get_available_destinations(
            session.current_location, session.gear_rented
        ),
    }
