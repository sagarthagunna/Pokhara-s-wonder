"""
app/agent/graph.py

The non-linear navigation graph from the spec:

    [Devi's Fall Overlook] <───> [Cave Entrance Plaza] <───> [Deep Cave Shivalaya]
              ▲                                                      ▲
              └──────────────(Unlocked with Flashlight & Helmet)─────┘

Modeled as a plain adjacency dict + a locking predicate. Kept dependency-free
on purpose (no networkx) so the logic is easy to read and easy to defend in
a viva/report: it's just a graph, edges, and one conditional edge.
"""

from dataclasses import dataclass, field


@dataclass
class LocationNode:
    id: str
    name: str
    description: str
    background_asset: str  # filename the frontend uses for the background
    connects_to: list[str] = field(default_factory=list)


LOCATIONS: dict[str, LocationNode] = {
    "devis_fall": LocationNode(
        id="devis_fall",
        name="Devi's Fall Overlook",
        description=(
            "You stand at the railed overlook above Patale Chhango, where the "
            "Pardi Khola thunders into a limestone sinkhole and vanishes underground."
        ),
        background_asset="devis_fall.jpg",
        connects_to=["entrance_plaza"],
    ),
    "entrance_plaza": LocationNode(
        id="entrance_plaza",
        name="Cave Entrance Plaza",
        description=(
            "The stone archway of Gupteshwor Mahadev Cave rises ahead, flanked by "
            "souvenir stalls, a ticket counter, and the gear vendor renting flashlights "
            "and helmets for the deeper passage."
        ),
        background_asset="entrance_plaza.jpg",
        connects_to=["devis_fall", "deep_shivalaya"],  # deep_shivalaya edge is conditional
    ),
    "deep_shivalaya": LocationNode(
        id="deep_shivalaya",
        name="Deep Cave Shivalaya",
        description=(
            "Damp limestone walls close in around you. Somewhere below, the same "
            "water that fell at Devi's Fall roars through the dark, unseen channel."
        ),
        background_asset="deep_shivalaya.jpg",
        connects_to=["entrance_plaza"],
    ),
}

# The one conditional edge in the graph, per the spec.
LOCKED_EDGE = {"from": "entrance_plaza", "to": "deep_shivalaya", "requires": "gear_rented"}


# Real-world travel directions between the graph's locations, keyed by
# (from, to) location id pairs. change_location() attaches the relevant
# route to its result so the agent can narrate "how to get there" as part
# of announcing the move.
#
# Note: "how do I reach Devi's Fall" style questions asked from OUTSIDE
# the graph entirely (before the visitor has arrived) are answered via
# look_up_artifact() instead, from the "How to reach Devi's Fall" section
# in app/rag/knowledge/devis_fall.txt — that's the single source of truth
# for arrival directions, kept separate from this graph-internal data so
# the two don't drift out of sync with each other.
TRAVEL_ROUTES = {
    ("devis_fall", "entrance_plaza"): (
        "Just cross the road from the Devi's Fall overlook — the Gupteshwor "
        "Cave archway is directly opposite, about a two-minute walk."
    ),
    ("entrance_plaza", "devis_fall"): (
        "Head back out through the archway and cross the road — Devi's Fall "
        "is right there, about a two-minute walk."
    ),
    ("entrance_plaza", "deep_shivalaya"): (
        "From the plaza, head down the spiral staircase past the ticket "
        "checkpoint. The passage narrows and slopes down toward the inner "
        "chamber — a few minutes' careful walk on wet stone."
    ),
    ("deep_shivalaya", "entrance_plaza"): (
        "Follow the passage back up the sloped walkway and staircase toward "
        "the daylight of the plaza."
    ),
}


def get_travel_route(from_location: str, to_location: str) -> str | None:
    """Returns the narrated travel instructions for a graph edge, if any."""
    return TRAVEL_ROUTES.get((from_location, to_location))


def get_available_destinations(current_location: str, gear_rented: bool) -> list[str]:
    """
    Returns the list of location ids reachable from current_location right now,
    respecting the gear-lock condition on the entrance_plaza <-> deep_shivalaya edge.
    """
    node = LOCATIONS.get(current_location)
    if not node:
        return []

    destinations = []
    for dest in node.connects_to:
        if dest == "deep_shivalaya" and not gear_rented:
            continue  # locked
        if current_location == "deep_shivalaya" and dest == "entrance_plaza":
            destinations.append(dest)  # always allowed back out
            continue
        destinations.append(dest)
    return destinations


def is_move_allowed(from_location: str, to_location: str, gear_rented: bool) -> tuple[bool, str]:
    """
    Validates a proposed move. Returns (allowed, reason_if_not_allowed).
    """
    node = LOCATIONS.get(from_location)
    if not node:
        return False, f"Unknown current location '{from_location}'."
    if to_location not in node.connects_to:
        return False, f"'{to_location}' is not directly connected to '{from_location}'."
    if to_location == "deep_shivalaya" and not gear_rented:
        return False, (
            "The Deep Cave Shivalaya is locked. You need to rent a Flashlight & "
            "Safety Helmet from the gear vendor at the Cave Entrance Plaza first."
        )
    return True, ""