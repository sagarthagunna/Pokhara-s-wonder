"""
app/tools/calculate_subterranean_risk.py

Required tool #3 (scenario-specific custom tool):
    calculate_subterranean_risk(humidity_pct: float, water_flow_lps: float)

Determines whether the Deep Cave Shivalaya is safe to enter right now,
based on simulated seasonal readings. This models a real constraint
mentioned in the knowledge base: the cave's inner passage is sometimes
closed during monsoon season when water from the waterfall floods
sections of the route, and high humidity signals a saturated, slippery,
poor-visibility chamber.

Thresholds (documented here so grading/reporting is transparent about
where these numbers come from — they are reasonable domain assumptions
for a Himalayan karst cave, not measured field data):

  water_flow_lps:
    < 300   -> low / dry-season flow, minimal risk from water
    300-800 -> moderate, typical shoulder-season flow
    > 800   -> high, monsoon-level flow -> flooding risk in low passages

  humidity_pct:
    < 85    -> normal cave dampness
    85-95   -> high humidity, condensation, slick surfaces
    > 95    -> saturated air, standing water likely, poor visibility
"""

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculate_subterranean_risk",
        "description": (
            "Assess whether the Deep Cave Shivalaya is currently safe to enter, "
            "based on humidity and underground water flow readings. Use this "
            "before encouraging the visitor to proceed into the deep cave, "
            "especially if they ask 'is it safe' or during monsoon-season context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "humidity_pct": {
                    "type": "number",
                    "description": "Relative humidity inside the cave chamber, as a percentage (0-100).",
                },
                "water_flow_lps": {
                    "type": "number",
                    "description": "Underground stream flow rate in liters per second.",
                },
            },
            "required": ["humidity_pct", "water_flow_lps"],
        },
    },
}


def calculate_subterranean_risk(humidity_pct: float, water_flow_lps: float) -> dict:
    humidity_pct = max(0.0, min(100.0, humidity_pct))
    water_flow_lps = max(0.0, water_flow_lps)

    # Weighted risk score: water flow matters slightly more than humidity,
    # since flooding is the more acute physical danger.
    humidity_score = humidity_pct / 100
    flow_score = min(water_flow_lps / 1000, 1.0)
    risk_score = round((humidity_score * 0.4) + (flow_score * 0.6), 3)

    if risk_score < 0.4:
        verdict = "safe"
        message = "Conditions are within normal range. Safe for tourist entry."
    elif risk_score < 0.7:
        verdict = "caution"
        message = (
            "Elevated humidity and/or water flow detected. Entry is possible but "
            "visitors should move carefully, wear the rented helmet and use the "
            "flashlight, and be prepared to turn back if conditions worsen."
        )
    else:
        verdict = "unsafe"
        message = (
            "High water flow and/or humidity indicate monsoon-level conditions. "
            "The passage is at meaningful flooding risk — entry is not recommended "
            "at this time."
        )

    return {
        "risk_score": risk_score,
        "verdict": verdict,
        "message": message,
        "inputs": {"humidity_pct": humidity_pct, "water_flow_lps": water_flow_lps},
    }
