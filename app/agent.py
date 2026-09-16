import json
import data_tools
from strands import Agent, tool
from strands.models import BedrockModel

MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

SYSTEM_PROMPT = """You are a senior predictive maintenance engineer for a crude distillation unit (CDU) with 12 centrifugal pumps (P-01 through P-12). You have access to real sensor data, maintenance records, failure history, OEM manuals, and spare parts inventory.

Your job: analyze pump health, diagnose anomalies, predict failures, and recommend actions.

CRITICAL RULES:
1. ALWAYS use tools to get data before making claims. Never guess sensor values or maintenance dates.
2. EVERY number you cite must come from a tool result. Include the source (file name, pump ID, date) in your answer.
3. If the data doesn't support a conclusion, say so explicitly rather than speculating.
4. When diagnosing, cross-reference: sensor readings → failure_mode_reference → OEM manual → maintenance history → spare parts.
5. Format your response with clear sections. Use markdown.
6. For vibration analysis, compare against the pump's specific baselines from vibration_baselines.csv — each pump has different normals.
7. When recommending parts or actions, check spare_parts_inventory for availability and lead times.
8. Be CONCISE. Keep responses under 500 words. Use tables for data, not prose. Only call the 2-3 most relevant tools per question — do not exhaustively query every data source.
9. For general questions, start with get_fleet_overview or get_pump_latest_readings. Only dig deeper if the user asks for details.

The dataset covers September 2025 through February 2026. There are 8 known failure events in this period across 6 pumps.

Pump models and their OEM manuals:
- Flowserve PVXM-3 (P-01, P-02, P-07, P-10) — crude oil
- Sulzer CPT-50 (P-03, P-04, P-08, P-11) — naphtha/kerosene
- KSB Etanorm 100-080 (P-05, P-06, P-09, P-12) — diesel/fuel oil"""


# ---------------------------------------------------------------------------
# Strands @tool definitions — wrappers around data_tools functions
# ---------------------------------------------------------------------------

@tool
def get_pump_latest_readings(pump_id: str) -> dict:
    """Get the most recent sensor readings for a specific pump, including comparison against operating envelope limits."""
    return data_tools.get_pump_latest_readings(pump_id)


@tool
def get_pump_sensor_history(pump_id: str, hours: int = 24) -> dict:
    """Get sensor reading statistics (min, max, mean, trend) over a time window for a pump. Use this to detect trends. Use 168 for a week, 720 for a month."""
    return data_tools.get_pump_sensor_history(pump_id, hours)


@tool
def get_pump_metadata(pump_id: str) -> dict:
    """Get pump specifications: model, manufacturer, service fluid, operating envelope, bearing/seal type, criticality rating."""
    return data_tools.get_pump_metadata(pump_id)


@tool
def get_maintenance_history(pump_id: str) -> dict:
    """Get combined maintenance history from both the service log (59 records, JSON) and CMMS work orders (120 records, CSV) for a pump."""
    return data_tools.get_maintenance_history(pump_id)


@tool
def get_failure_mode_reference(failure_mode: str = "") -> list:
    """Look up failure mode sensor signatures, lead times, and recommended actions. Pass a specific mode (bearing_wear, seal_failure, cavitation, impeller_damage, misalignment) or empty string for all."""
    return data_tools.get_failure_mode_reference(failure_mode)


@tool
def get_failure_events(pump_id: str = "") -> list:
    """Get historical failure events with downtime and repair costs. Filter by pump_id or get all 8 events."""
    return data_tools.get_failure_events(pump_id)


@tool
def get_vibration_baselines(pump_id: str) -> list:
    """Get established per-pump vibration baselines with alert/alarm/trip thresholds per axis. Essential for comparing current vibration against what's normal for this specific pump."""
    return data_tools.get_vibration_baselines(pump_id)


@tool
def get_alarm_history(pump_id: str = "") -> list:
    """Get alarm events for a pump. Most are nuisance alarms, but patterns matter."""
    return data_tools.get_alarm_history(pump_id)


@tool
def get_spare_parts(pump_id: str = "") -> list:
    """Check spare parts inventory — stock levels, lead times, costs, and which pumps each part is compatible with."""
    return data_tools.get_spare_parts(pump_id)


@tool
def get_cost_tracking(pump_id: str) -> list:
    """Get monthly maintenance, energy, and parts cost breakdown for a pump."""
    return data_tools.get_cost_tracking(pump_id)


@tool
def get_operating_schedule(pump_id: str) -> list:
    """Get recent operating schedule — duty state, load percentage, assigned process, cumulative run hours."""
    return data_tools.get_operating_schedule(pump_id)


@tool
def get_oem_manual_section(model: str, search_term: str = "") -> dict:
    """Read OEM equipment manual for a pump model. Use search_term to find specific sections (e.g. 'vibration', 'bearing', 'seal', 'troubleshooting', 'lubrication'). Models: 'Flowserve PVXM-3', 'KSB Etanorm 100-080', 'Sulzer CPT-50'."""
    return data_tools.get_oem_manual_section(model, search_term)


@tool
def get_fleet_overview(snapshot_ts: str = "") -> list:
    """Get all 12 pumps with current readings, health score, and metadata. Pass snapshot_ts (ISO timestamp) to view fleet at a specific point in time."""
    return data_tools.get_fleet_overview(snapshot_ts)


# ---------------------------------------------------------------------------
# All tools list
# ---------------------------------------------------------------------------

TOOLS = [
    get_pump_latest_readings,
    get_pump_sensor_history,
    get_pump_metadata,
    get_maintenance_history,
    get_failure_mode_reference,
    get_failure_events,
    get_vibration_baselines,
    get_alarm_history,
    get_spare_parts,
    get_cost_tracking,
    get_operating_schedule,
    get_oem_manual_section,
    get_fleet_overview,
]


# ---------------------------------------------------------------------------
# Agent factory and session management
# ---------------------------------------------------------------------------

_model = BedrockModel(
    model_id=MODEL_ID,
    region_name="us-east-1",
    max_tokens=4096,
    temperature=0.1,
)

_sessions: dict[str, Agent] = {}


def _get_agent(session_id: str) -> Agent:
    """Get or create a Strands Agent for a session."""
    if session_id not in _sessions:
        _sessions[session_id] = Agent(
            model=_model,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
        )
    return _sessions[session_id]


def reset_session(session_id: str):
    """Clear a session's agent."""
    _sessions.pop(session_id, None)


def chat(user_message: str, session_id: str = "default", conversation_history: list = None) -> dict:
    """Send a message to the Strands agent, return final response."""
    agent = _get_agent(session_id)

    tool_calls_made = []
    response_text = ""

    result = agent(user_message)
    response_text = str(result)

    for msg in agent.messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if "toolUse" in block:
                    tool_calls_made.append({
                        "tool": block["toolUse"]["name"],
                        "input": block["toolUse"].get("input", {}),
                    })

    return {
        "response": response_text,
        "tool_calls": tool_calls_made,
        "conversation_history": agent.messages,
    }
