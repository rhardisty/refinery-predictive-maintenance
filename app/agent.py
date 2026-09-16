import json
import data_tools
from strands import Agent, tool
from strands.models import BedrockModel

MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


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
# Shared model
# ---------------------------------------------------------------------------

_model = BedrockModel(
    model_id=MODEL_ID,
    region_name="us-east-1",
    max_tokens=4096,
    temperature=0.1,
)

# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------

SHARED_CONTEXT = """The CDU has 12 centrifugal pumps (P-01 through P-12). Dataset covers September 2025 through February 2026 with 8 known failure events.
Pump models: Flowserve PVXM-3 (P-01,P-02,P-07,P-10 — crude oil), Sulzer CPT-50 (P-03,P-04,P-08,P-11 — naphtha/kerosene), KSB Etanorm 100-080 (P-05,P-06,P-09,P-12 — diesel/fuel oil).
EVERY claim must cite its data source (file name, pump ID, date). Never guess values."""

diagnosis_agent = Agent(
    name="diagnosis_specialist",
    description="Diagnose pump health issues by analyzing sensor data, vibration baselines, failure mode signatures, and alarm patterns. Delegate to this agent when the user asks about a specific pump's condition, anomalies, sensor readings, vibration analysis, or failure risk prediction.",
    model=_model,
    tools=[
        get_pump_latest_readings,
        get_pump_sensor_history,
        get_pump_metadata,
        get_vibration_baselines,
        get_failure_mode_reference,
        get_failure_events,
        get_alarm_history,
    ],
    system_prompt=f"""You are a Pump Diagnosis Specialist for a crude distillation unit.
Your expertise: sensor data analysis, vibration analysis (ISO 10816), failure mode pattern matching, and anomaly detection.

{SHARED_CONTEXT}

WORKFLOW:
1. Pull current readings and compare against operating envelope
2. Check vibration against this pump's specific baselines (not generic limits)
3. Match sensor patterns against failure_mode_reference signatures
4. Review alarm history for correlated events
5. Assess failure risk with estimated lead time

Be precise with numbers. Use tables for sensor data. State confidence level in your diagnosis.
Keep your response under 300 words. Only call the 2-3 most relevant tools — do not query every data source.""",
)

maintenance_agent = Agent(
    name="maintenance_specialist",
    description="Analyze maintenance history, recommend repair actions, check OEM manual guidance, and verify spare parts availability. Delegate to this agent for maintenance planning, work order review, OEM manual lookups, spare parts checks, or repair recommendations.",
    model=_model,
    tools=[
        get_maintenance_history,
        get_oem_manual_section,
        get_spare_parts,
        get_pump_metadata,
        get_failure_events,
        get_cost_tracking,
        get_operating_schedule,
    ],
    system_prompt=f"""You are a Maintenance Planning Specialist for a crude distillation unit.
Your expertise: maintenance scheduling, OEM manual interpretation, spare parts logistics, work order analysis, and repair cost optimization.

{SHARED_CONTEXT}

WARNING: The two maintenance logs (pump_maintenance_history.json and maintenance_work_orders.csv) have separate ID spaces. NEVER join on work_order_id.

WORKFLOW:
1. Review maintenance history from both logs
2. Cross-reference OEM manual for recommended intervals and procedures
3. Check spare parts availability and lead times
4. Estimate repair effort and cost
5. Recommend prioritized actions with timeline

Always check parts inventory before recommending replacements. Flag any parts with zero stock or long lead times.
Keep your response under 300 words. Only call the 2-3 most relevant tools.""",
)

fleet_agent = Agent(
    name="fleet_analyst",
    description="Analyze fleet-wide trends, compare pumps, track costs across the fleet, and identify systemic patterns. Delegate to this agent for fleet overviews, cross-pump comparisons, cost analysis, downtime summaries, or questions about multiple pumps.",
    model=_model,
    tools=[
        get_fleet_overview,
        get_failure_events,
        get_cost_tracking,
        get_operating_schedule,
        get_spare_parts,
        get_pump_metadata,
        get_alarm_history,
    ],
    system_prompt=f"""You are a Fleet Analyst for a crude distillation unit's pump fleet.
Your expertise: fleet-wide health trends, comparative analysis, cost optimization, downtime impact assessment, and reliability patterns.

{SHARED_CONTEXT}

WORKFLOW:
1. Get fleet overview for current state
2. Identify pumps with lowest health scores or active flags
3. Cross-reference failure history for pattern detection
4. Analyze cost trends to find outliers
5. Prioritize fleet-wide recommendations by criticality and risk

Use tables for comparisons. Rank pumps by risk. Quantify cost impact where possible.
Keep your response under 300 words. Only call the 2-3 most relevant tools.""",
)


# ---------------------------------------------------------------------------
# Supervisor agent — orchestrates specialists
# ---------------------------------------------------------------------------

SUPERVISOR_PROMPT = f"""You are the Lead Predictive Maintenance Engineer supervising a team of three specialists for a CDU pump fleet. You coordinate their expertise to answer questions.

{SHARED_CONTEXT}

YOUR SPECIALISTS:
- **diagnosis_specialist**: Sensor analysis, vibration diagnostics, failure mode matching, anomaly detection. Use for questions about specific pump health, sensor readings, or failure prediction.
- **maintenance_specialist**: Maintenance history, OEM manuals, spare parts, repair planning, costs. Use for maintenance scheduling, repair recommendations, or parts availability.
- **fleet_analyst**: Fleet-wide overviews, cross-pump comparisons, cost trends, systemic patterns. Use for questions about multiple pumps, fleet health, or cost analysis.

RULES:
1. ALWAYS delegate to exactly ONE specialist per question — pick the best fit.
2. For questions about a specific pump's condition, sensors, or failure risk → diagnosis_specialist.
3. For maintenance, repair, OEM manual, or spare parts questions → maintenance_specialist.
4. For fleet-wide, comparative, cost, or multi-pump questions → fleet_analyst.
5. Pass the user's full question to the specialist. The specialist's response IS your final answer — relay it directly.
6. Do NOT add your own commentary or re-summarize the specialist's response."""


def _build_supervisor() -> Agent:
    """Create a supervisor agent with specialist sub-agents as tools."""
    return Agent(
        model=_model,
        tools=[
            diagnosis_agent.as_tool(),
            maintenance_agent.as_tool(),
            fleet_agent.as_tool(),
        ],
        system_prompt=SUPERVISOR_PROMPT,
    )


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

_sessions: dict[str, Agent] = {}


def _get_agent(session_id: str) -> Agent:
    """Get or create a supervisor agent for a session."""
    if session_id not in _sessions:
        _sessions[session_id] = _build_supervisor()
    return _sessions[session_id]


def reset_session(session_id: str):
    """Clear a session's agent."""
    _sessions.pop(session_id, None)


def chat(user_message: str, session_id: str = "default", conversation_history: list = None) -> dict:
    """Send a message to the multi-agent system, return final response."""
    supervisor = _get_agent(session_id)

    result = supervisor(user_message)
    response_text = str(result)

    tool_calls_made = []
    for msg in supervisor.messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if "toolUse" in block:
                    name = block["toolUse"]["name"]
                    tool_calls_made.append({
                        "tool": name,
                        "input": block["toolUse"].get("input", {}),
                    })

    return {
        "response": response_text,
        "tool_calls": tool_calls_made,
        "conversation_history": supervisor.messages,
    }
