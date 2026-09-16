# Refinery Predictive Maintenance Agent — Team Plan

## Hackathon: Claude Code + Bedrock AgentCore · Energy Symposium

---

## Team Roles (5 members)

### Person 1 — Data Engineer
**Owns:** sensor pipeline, data access tools, anomaly detection logic

- Write Python scripts that query `sensor_timeseries.csv` (625K rows) efficiently — never load it all at once. Use pandas/polars to compute per-pump rolling stats (mean, std, z-scores) for each sensor channel.
- Build the **anomaly detection module**: compare readings against `vibration_baselines.csv` (per-pump normals) and ISO 10816 zone thresholds from `failure_mode_reference.csv`.
- Compute health scores per pump. Flag when readings cross from Zone B→C or C→D.
- Expose these as **agent tools**: `get_pump_latest_readings(pump_id)`, `get_pump_health_score(pump_id)`, `detect_anomalies(pump_id, window_hours)`, `get_sensor_trend(pump_id, sensor, hours)`.
- Validate against `failure_event_log.csv` — can your detection flag the 8 known failures during their `pre_failure` windows?

### Person 2 — Knowledge / Context Engineer
**Owns:** maintenance history, OEM manuals, failure-mode reasoning

- Parse and index the 3 OEM manuals (use the `.md` versions — easier to chunk). Build a tool that retrieves relevant manual sections given a failure mode or symptom.
- Build tools over the maintenance data:
  - `get_maintenance_history(pump_id)` — merges both `pump_maintenance_history.json` (59 records) and `maintenance_work_orders.csv` (120 records). **Do NOT join on work_order_id** — match on `pump_id` + nearby dates instead.
  - `get_pump_metadata(pump_id)` — returns pump specs, install date, which OEM manual applies.
  - `check_spare_parts(part_name)` — queries `spare_parts_inventory.csv` for stock & lead times.
  - `get_alarm_history(pump_id)` — filters `alarm_history.csv`.
- Build the **failure diagnosis lookup**: given a sensor signature, match to `failure_mode_reference.csv` → failure mode, lead time, recommended action.

### Person 3 — Agent Architect / Orchestrator
**Owns:** agent design, multi-agent orchestration, Strands SDK integration

- Design the agent architecture. Recommended pattern — **supervisor + specialists**:
  - **Supervisor agent**: receives a query, decides which specialist(s) to call, synthesizes the final grounded answer.
  - **Sensor analyst agent**: uses Person 1's tools.
  - **Maintenance advisor agent**: uses Person 2's tools.
- Wire up all tools from Persons 1 & 2 as Strands agent tools.
- Ensure every response is **grounded** — cite which file, row, or manual passage backs each claim. (This is a judging criterion.)

### Person 4 — Frontend / Demo Developer
**Owns:** the UI, the demo experience, visualization

- Build a web dashboard (React, Streamlit, or plain HTML). Run on **port 3000** (not 8080 — that's the editor).
- Key views:
  - **Fleet overview**: 12 pumps, color-coded by health score (green/yellow/red).
  - **Pump detail**: sensor trends, anomaly highlights, maintenance timeline.
  - **Chat interface**: ask the agent questions, see grounded responses with citations.
  - **Alert feed**: recent anomalies ranked by severity.
- Polish > features. Judges score the working demo.

### Person 5 — Deployment & Integration Lead
**Owns:** AgentCore deployment, testing, end-to-end validation

- Set up AgentCore project structure (`agentcore dev --port 3000` for local testing).
- Deploy the agent to Bedrock AgentCore for the final demo.
- Write the **validation suite**: test the agent against all 8 known failures in `failure_event_log.csv`.
- Own `operating_schedule.csv` and `cost_tracking.csv` integration.
- Prepare the demo script — the sequence of scenarios to show judges.

---

## Execution Plan

### Phase 1 — Foundation (first ~2 hours)
| Who | Does what |
|---|---|
| Person 1 | Unzip data, explore CSVs, build anomaly detection scripts, validate against 8 known failures |
| Person 2 | Parse OEM manuals, build maintenance/diagnosis lookup tools |
| Person 3 | Scaffold the Strands agent project, define tool interfaces |
| Person 4 | Scaffold the frontend, build fleet overview with mock data |
| Person 5 | Set up AgentCore project, write validation harness |

### Phase 2 — Integration (next ~2 hours)
| Who | Does what |
|---|---|
| Person 1 | Plug anomaly tools into agent framework |
| Person 2 | Plug knowledge tools into agent framework |
| Person 3 | Wire up supervisor orchestration, test multi-agent flow |
| Person 4 | Connect frontend to live agent API, replace mocks |
| Person 5 | Test full pipeline locally, fix integration issues |

### Phase 3 — Polish & Deploy (final ~2 hours)
| Who | Does what |
|---|---|
| All | Fix bugs from integration testing |
| Person 3 | Tune prompts for grounded citations |
| Person 4 | Polish UI, add demo highlights |
| Person 5 | Deploy to AgentCore, run validation, rehearse demo |

---

## Critical Rules

1. **Grounding is everything.** Every answer must cite file + row/passage. Build this into system prompts early.
2. **Don't read the 60MB CSV into an LLM.** Use Python tools that query and return summaries.
3. **Two maintenance logs = separate ID spaces.** Never join on `work_order_id`. Match on `pump_id` + nearby dates.
4. **Port 8080 = your editor.** Run everything else on 3000+.
5. **Demo > features.** 3 polished scenarios beat 10 half-working ones.

---

## Resources

- Claude Code docs: https://docs.claude.com/en/docs/claude-code
- Strands Agents SDK: https://strandsagents.com
- Amazon Bedrock AgentCore: https://docs.aws.amazon.com/bedrock-agentcore/
