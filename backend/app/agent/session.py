"""
app/agent/session.py

Minimal in-memory session store. For a single-user, one-hour-session demo
app (as scoped by this assignment) a persistent database is overkill —
a dict keyed by session_id is enough, and it's easy to explain in a report.

If you needed multi-user persistence beyond the process lifetime, this is
the one place you'd swap out (e.g. for Redis) without touching any other
file, since everything else talks to sessions through get_session().
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class SessionState:
    session_id: str
    current_location: str = "devis_fall"
    gear_rented: bool = False
    history: list[dict] = field(default_factory=list)  # chat messages, role/content


_sessions: dict[str, SessionState] = {}


def create_session() -> SessionState:
    sid = str(uuid.uuid4())
    session = SessionState(session_id=sid)
    _sessions[sid] = session
    return session


def get_session(session_id: str) -> SessionState | None:
    return _sessions.get(session_id)


def get_or_create(session_id: str | None) -> SessionState:
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    return create_session()
