"""
app/tools/look_up_artifact.py

Required tool #1: look_up_artifact()

Lets the agent pull facts about something the visitor asks about
("how deep is the sinkhole?", "when was the cave found?"), but ONLY from
the knowledge belonging to the visitor's CURRENT location — this is what
enforces the "RAG Boundaries" from the spec at the tool level, not just
in the retriever.
"""

from app.rag.retriever import query_location

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "look_up_artifact",
        "description": (
            "Look up factual information about an artifact, feature, or topic at "
            "the visitor's CURRENT location (e.g. 'sinkhole depth', 'ticket price', "
            "'stalactites', 'cave discovery history'). Only returns information "
            "relevant to where the visitor currently is standing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What the visitor wants to know about, in natural language.",
                }
            },
            "required": ["query"],
        },
    },
}


def look_up_artifact(query: str, current_location: str) -> dict:
    hits = query_location(location=current_location, query=query, n_results=3)

    if not hits:
        return {
            "found": False,
            "message": f"No information found for '{query}' at this location.",
        }

    return {
        "found": True,
        "location": current_location,
        "results": [h["text"] for h in hits],
    }
