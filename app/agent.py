import boto3
import json
import data_tools

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
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

The dataset covers September 2025 through February 2026. There are 8 known failure events in this period across 6 pumps.

Pump models and their OEM manuals:
- Flowserve PVXM-3 (P-01, P-02, P-07, P-10) — crude oil
- Sulzer CPT-50 (P-03, P-04, P-08, P-11) — naphtha/kerosene
- KSB Etanorm 100-080 (P-05, P-06, P-09, P-12) — diesel/fuel oil"""

TOOLS = [
    {
        "toolSpec": {
            "name": "get_pump_latest_readings",
            "description": "Get the most recent sensor readings for a specific pump, including comparison against operating envelope limits.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, e.g. P-01"}
                    },
                    "required": ["pump_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_pump_sensor_history",
            "description": "Get sensor reading statistics (min, max, mean, trend) over a time window for a pump. Use this to detect trends.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, e.g. P-01"},
                        "hours": {"type": "integer", "description": "Hours of history to analyze. Default 24. Use 168 for a week, 720 for a month.", "default": 24},
                    },
                    "required": ["pump_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_pump_metadata",
            "description": "Get pump specifications: model, manufacturer, service fluid, operating envelope, bearing/seal type, criticality rating.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, e.g. P-01"}
                    },
                    "required": ["pump_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_maintenance_history",
            "description": "Get combined maintenance history from both the service log (59 records, JSON) and CMMS work orders (120 records, CSV) for a pump.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, e.g. P-01"}
                    },
                    "required": ["pump_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_failure_mode_reference",
            "description": "Look up failure mode sensor signatures, lead times, and recommended actions. Pass a specific mode (bearing_wear, seal_failure, cavitation, impeller_damage, misalignment) or empty string for all.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "failure_mode": {"type": "string", "description": "Failure mode name, or empty string for all modes", "default": ""},
                    },
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_failure_events",
            "description": "Get historical failure events with downtime and repair costs. Filter by pump_id or get all 8 events.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID to filter, or empty for all", "default": ""},
                    },
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_vibration_baselines",
            "description": "Get established per-pump vibration baselines with alert/alarm/trip thresholds per axis. Essential for comparing current vibration against what's normal for this specific pump.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, e.g. P-01"}
                    },
                    "required": ["pump_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_alarm_history",
            "description": "Get alarm events for a pump. Most are nuisance alarms, but patterns matter.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, or empty for all", "default": ""},
                    },
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_spare_parts",
            "description": "Check spare parts inventory — stock levels, lead times, costs, and which pumps each part is compatible with.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Filter to parts compatible with this pump, or empty for all", "default": ""},
                    },
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_cost_tracking",
            "description": "Get monthly maintenance, energy, and parts cost breakdown for a pump.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, e.g. P-01"}
                    },
                    "required": ["pump_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_operating_schedule",
            "description": "Get recent operating schedule — duty state, load percentage, assigned process, cumulative run hours.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "pump_id": {"type": "string", "description": "Pump ID, e.g. P-01"}
                    },
                    "required": ["pump_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_oem_manual_section",
            "description": "Read OEM equipment manual for a pump model. Use search_term to find specific sections (e.g. 'vibration', 'bearing', 'seal', 'troubleshooting', 'lubrication').",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string", "description": "Pump model: 'Flowserve PVXM-3', 'KSB Etanorm 100-080', or 'Sulzer CPT-50'"},
                        "search_term": {"type": "string", "description": "Keyword to search for in the manual", "default": ""},
                    },
                    "required": ["model"],
                }
            },
        }
    },
]

TOOL_DISPATCH = {
    "get_pump_latest_readings": lambda args: data_tools.get_pump_latest_readings(args["pump_id"]),
    "get_pump_sensor_history": lambda args: data_tools.get_pump_sensor_history(args["pump_id"], args.get("hours", 24)),
    "get_pump_metadata": lambda args: data_tools.get_pump_metadata(args["pump_id"]),
    "get_maintenance_history": lambda args: data_tools.get_maintenance_history(args["pump_id"]),
    "get_failure_mode_reference": lambda args: data_tools.get_failure_mode_reference(args.get("failure_mode", "")),
    "get_failure_events": lambda args: data_tools.get_failure_events(args.get("pump_id", "")),
    "get_vibration_baselines": lambda args: data_tools.get_vibration_baselines(args["pump_id"]),
    "get_alarm_history": lambda args: data_tools.get_alarm_history(args.get("pump_id", "")),
    "get_spare_parts": lambda args: data_tools.get_spare_parts(args.get("pump_id", "")),
    "get_cost_tracking": lambda args: data_tools.get_cost_tracking(args["pump_id"]),
    "get_operating_schedule": lambda args: data_tools.get_operating_schedule(args["pump_id"]),
    "get_oem_manual_section": lambda args: data_tools.get_oem_manual_section(args["model"], args.get("search_term", "")),
}


def chat(user_message: str, conversation_history: list = None) -> dict:
    """Send a message to the agent, handle tool calls, return final response."""
    if conversation_history is None:
        conversation_history = []

    conversation_history.append({
        "role": "user",
        "content": [{"text": user_message}],
    })

    tool_calls_made = []
    max_turns = 10

    for _ in range(max_turns):
        response = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=conversation_history,
            toolConfig={"tools": TOOLS},
            inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
        )

        msg = response["output"]["message"]
        conversation_history.append(msg)
        stop = response["stopReason"]

        if stop == "tool_use":
            tool_results = []
            for block in msg["content"]:
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use["input"]
                    tool_id = tool_use["toolUseId"]

                    fn = TOOL_DISPATCH.get(tool_name)
                    if fn:
                        result = fn(tool_input)
                        tool_calls_made.append({"tool": tool_name, "input": tool_input})
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    if isinstance(result, list):
                        result = {"items": result}

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": [{"json": result}],
                        }
                    })

            conversation_history.append({
                "role": "user",
                "content": tool_results,
            })
        else:
            final_text = ""
            for block in msg["content"]:
                if "text" in block:
                    final_text += block["text"]

            return {
                "response": final_text,
                "tool_calls": tool_calls_made,
                "conversation_history": conversation_history,
            }

    return {
        "response": "I ran out of analysis steps. Please try a more specific question.",
        "tool_calls": tool_calls_made,
        "conversation_history": conversation_history,
    }
