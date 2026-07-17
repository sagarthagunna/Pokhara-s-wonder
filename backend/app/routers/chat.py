"""
app/routers/chat.py

The main conversational endpoint. The frontend's speech-to-text (browser
Web Speech API) produces a transcript, POSTs it here, and gets back the
guide's reply text (which the frontend then feeds to speech-synthesis for
TTS) plus updated location/graph state for re-rendering backgrounds and
action chips.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.session import get_session
from app.agent.agent_loop import run_agent_turn

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("")
async def chat(payload: ChatRequest):
    session = get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Create one via /session/new.")

    result = await run_agent_turn(session, payload.message)
    return result
