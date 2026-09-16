import pandas as pd
import json
import os

DATA_DIR = "/workshop/data"

# ---------------------------------------------------------------------------
# Load data once at import time — 60MB sensor CSV is fine in RAM for a demo
# ---------------------------------------------------------------------------

_sensor_df = None
_pump_metadata_df = None
_failure_events_df = None
_failure_modes_df = None
_vibration_baselines_df = None
_alarm_history_df = None
_operating_schedule_df = None
_spare_parts_df = None
_cost_tracking_df = None
_work_orders_df = None
_maintenance_history = None


def _load():
    global _sensor_df, _pump_metadata_df, _failure_events_df, _failure_modes_df
    global _vibration_baselines_df, _alarm_history_df, _operating_schedule_df
    global _spare_parts_df, _cost_tracking_df, _work_orders_df, _maintenance_history

    if _pump_metadata_df is not None:
        return

    _pump_metadata_df = pd.read_csv(f"{DATA_DIR}/pump_metadata.csv")
    _failure_events_df = pd.read_csv(f"{DATA_DIR}/failure_event_log.csv")
    _failure_modes_df = pd.read_csv(f"{DATA_DIR}/failure_mode_reference.csv")
    _vibration_baselines_df = pd.read_csv(f"{DATA_DIR}/vibration_baselines.csv")
    _alarm_history_df = pd.read_csv(f"{DATA_DIR}/alarm_history.csv")
    _operating_schedule_df = pd.read_csv(f"{DATA_DIR}/operating_schedule.csv")
    _spare_parts_df = pd.read_csv(f"{DATA_DIR}/spare_parts_inventory.csv")
    _cost_tracking_df = pd.read_csv(f"{DATA_DIR}/cost_tracking.csv")
    _work_orders_df = pd.read_csv(f"{DATA_DIR}/maintenance_work_orders.csv")

    with open(f"{DATA_DIR}/pump_maintenance_history.json") as f:
        _maintenance_history = json.load(f)

    _sensor_df = pd.read_csv(
        f"{DATA_DIR}/sensor_timeseries.csv",
        parse_dates=["timestamp"],
        dtype={
            "pump_id": "category",
            "label": "category",
            "seal_leak_detected": "bool",
        },
    )


# ---------------------------------------------------------------------------
# Tool functions — each returns a dict/list ready for JSON serialization
# ---------------------------------------------------------------------------

def get_fleet_overview(snapshot_ts: str = "") -> list[dict]:
    """Get all 12 pumps with readings, health score, and metadata.
    Pass snapshot_ts (ISO timestamp) to view fleet at a specific point in time.
    """
    _load()
    results = []
    for _, pump in _pump_metadata_df.iterrows():
        pid = pump["pump_id"]
        envelope = json.loads(pump["operating_envelope_json"])

        pump_data = _sensor_df[_sensor_df["pump_id"] == pid]
        if snapshot_ts:
            pump_data = pump_data[pump_data["timestamp"] <= snapshot_ts]
        if pump_data.empty:
            continue
        latest = pump_data.iloc[-1]

        window = pump_data.tail(24)
        health = _compute_health(latest, envelope, pid, window)

        failures = _failure_events_df[_failure_events_df["pump_id"] == pid]
        last_failure = None
        if len(failures) > 0:
            row = failures.iloc[-1]
            last_failure = {
                "mode": row["failure_mode"],
                "date": row["failure_ts"],
                "downtime_hrs": float(row["downtime_hrs"]),
                "cost_usd": float(row["repair_cost_usd"]),
            }

        repair_req = _get_repair_requirements(pump)

        results.append({
            "pump_id": pid,
            "model": pump["model"],
            "manufacturer": pump["manufacturer"],
            "service_fluid": pump["service_fluid"],
            "criticality": int(pump["criticality_rating"]),
            "health_score": health["score"],
            "health_status": health["status"],
            "health_flags": health["flags"],
            "label": latest["label"],
            "bearing_temp_c": round(float(latest["bearing_temp_c"]), 1),
            "vibration_x": round(float(latest["vibration_x_mms"]), 2),
            "vibration_y": round(float(latest["vibration_y_mms"]), 2),
            "vibration_axial": round(float(latest["vibration_axial_mms"]), 2),
            "flow_rate": round(float(latest["flow_rate_m3hr"]), 1),
            "motor_current": round(float(latest["motor_current_amps"]), 1),
            "seal_leak": bool(latest["seal_leak_detected"]),
            "last_failure": last_failure,
            "last_maintenance": pump["last_maintenance_date"],
            "repair_requirements": repair_req,
        })
    return results


def get_pump_latest_readings(pump_id: str) -> dict:
    """Get the most recent sensor readings for a specific pump with context."""
    _load()
    readings = _sensor_df[_sensor_df["pump_id"] == pump_id]
    if readings.empty:
        return {"error": f"No data for pump {pump_id}"}

    latest = readings.iloc[-1]
    pump_meta = _pump_metadata_df[_pump_metadata_df["pump_id"] == pump_id].iloc[0]
    envelope = json.loads(pump_meta["operating_envelope_json"])

    return {
        "pump_id": pump_id,
        "timestamp": str(latest["timestamp"]),
        "readings": {
            "bearing_temp_c": round(float(latest["bearing_temp_c"]), 2),
            "vibration_x_mms": round(float(latest["vibration_x_mms"]), 3),
            "vibration_y_mms": round(float(latest["vibration_y_mms"]), 3),
            "vibration_axial_mms": round(float(latest["vibration_axial_mms"]), 3),
            "suction_pressure_psi": round(float(latest["suction_pressure_psi"]), 2),
            "discharge_pressure_psi": round(float(latest["discharge_pressure_psi"]), 2),
            "differential_pressure_psi": round(float(latest["differential_pressure_psi"]), 2),
            "flow_rate_m3hr": round(float(latest["flow_rate_m3hr"]), 2),
            "motor_current_amps": round(float(latest["motor_current_amps"]), 2),
            "motor_speed_rpm": int(latest["motor_speed_rpm"]),
            "seal_leak_detected": bool(latest["seal_leak_detected"]),
        },
        "label": latest["label"],
        "operating_envelope": envelope,
        "source": "sensor_timeseries.csv, last row for " + pump_id,
    }


def get_pump_sensor_history(pump_id: str, hours: int = 24) -> dict:
    """Get sensor history for a pump over the last N hours. Returns summary stats and trend."""
    _load()
    readings = _sensor_df[_sensor_df["pump_id"] == pump_id]
    if readings.empty:
        return {"error": f"No data for pump {pump_id}"}

    latest_ts = readings["timestamp"].max()
    cutoff = latest_ts - pd.Timedelta(hours=hours)
    window = readings[readings["timestamp"] >= cutoff]

    sensor_cols = [
        "bearing_temp_c", "vibration_x_mms", "vibration_y_mms",
        "vibration_axial_mms", "suction_pressure_psi", "discharge_pressure_psi",
        "differential_pressure_psi", "flow_rate_m3hr", "motor_current_amps",
    ]

    stats = {}
    for col in sensor_cols:
        vals = window[col].astype(float)
        stats[col] = {
            "min": round(vals.min(), 2),
            "max": round(vals.max(), 2),
            "mean": round(vals.mean(), 2),
            "latest": round(vals.iloc[-1], 2),
            "trend": "rising" if vals.iloc[-1] > vals.iloc[0] else "falling" if vals.iloc[-1] < vals.iloc[0] else "stable",
        }

    labels_in_window = window["label"].value_counts().to_dict()

    return {
        "pump_id": pump_id,
        "window_hours": hours,
        "from": str(cutoff),
        "to": str(latest_ts),
        "num_readings": len(window),
        "sensor_stats": stats,
        "labels_in_window": labels_in_window,
        "source": f"sensor_timeseries.csv, {len(window)} rows for {pump_id} in last {hours}h",
    }


def get_pump_metadata(pump_id: str) -> dict:
    """Get pump specifications, model, manufacturer, operating envelope."""
    _load()
    row = _pump_metadata_df[_pump_metadata_df["pump_id"] == pump_id]
    if row.empty:
        return {"error": f"No metadata for pump {pump_id}"}
    r = row.iloc[0]
    return {
        "pump_id": pump_id,
        "model": r["model"],
        "manufacturer": r["manufacturer"],
        "install_date": r["install_date"],
        "service_fluid": r["service_fluid"],
        "design_flow_m3hr": float(r["design_flow_m3hr"]),
        "design_head_m": float(r["design_head_m"]),
        "rated_power_kw": float(r["rated_power_kw"]),
        "criticality_rating": int(r["criticality_rating"]),
        "bearing_type": r["bearing_type"],
        "seal_type": r["seal_type"],
        "last_maintenance_date": r["last_maintenance_date"],
        "operating_envelope": json.loads(r["operating_envelope_json"]),
        "source": "pump_metadata.csv",
    }


def get_maintenance_history(pump_id: str) -> dict:
    """Get combined maintenance history from both log sources for a pump."""
    _load()

    json_records = [r for r in _maintenance_history if r["pump_id"] == pump_id]

    csv_records = _work_orders_df[_work_orders_df["pump_id"] == pump_id]
    csv_list = csv_records.to_dict("records")

    return {
        "pump_id": pump_id,
        "service_log_records": json_records,
        "service_log_source": f"pump_maintenance_history.json ({len(json_records)} records)",
        "work_order_records": csv_list,
        "work_order_source": f"maintenance_work_orders.csv ({len(csv_list)} records)",
        "warning": "These are two independent logs with different ID spaces. Do not join on work_order_id.",
    }


def get_failure_mode_reference(failure_mode: str = "") -> list[dict]:
    """Look up failure mode signatures. Pass a specific mode or empty for all."""
    _load()
    if failure_mode:
        rows = _failure_modes_df[_failure_modes_df["failure_mode"] == failure_mode]
    else:
        rows = _failure_modes_df
    result = rows.to_dict("records")
    for r in result:
        r["source"] = "failure_mode_reference.csv"
    return result


def get_failure_events(pump_id: str = "") -> list[dict]:
    """Get historical failure events. Filter by pump_id or get all."""
    _load()
    if pump_id:
        rows = _failure_events_df[_failure_events_df["pump_id"] == pump_id]
    else:
        rows = _failure_events_df
    result = rows.to_dict("records")
    for r in result:
        r["source"] = "failure_event_log.csv"
    return result


def get_vibration_baselines(pump_id: str) -> list[dict]:
    """Get established vibration baselines for a pump (per axis)."""
    _load()
    rows = _vibration_baselines_df[_vibration_baselines_df["pump_id"] == pump_id]
    result = rows.to_dict("records")
    for r in result:
        r["source"] = "vibration_baselines.csv"
    return result


def get_alarm_history(pump_id: str = "") -> list[dict]:
    """Get alarm history for a pump or all pumps."""
    _load()
    if pump_id:
        rows = _alarm_history_df[_alarm_history_df["pump_id"] == pump_id]
    else:
        rows = _alarm_history_df
    result = rows.to_dict("records")
    for r in result:
        r["source"] = "alarm_history.csv"
    return result


def get_spare_parts(pump_id: str = "") -> list[dict]:
    """Get spare parts inventory. Filter to parts compatible with a specific pump."""
    _load()
    if pump_id:
        rows = _spare_parts_df[_spare_parts_df["compatible_pumps"].str.contains(pump_id, na=False)]
    else:
        rows = _spare_parts_df
    result = rows.to_dict("records")
    for r in result:
        r["source"] = "spare_parts_inventory.csv"
    return result


def get_cost_tracking(pump_id: str) -> list[dict]:
    """Get monthly cost breakdown for a pump."""
    _load()
    rows = _cost_tracking_df[_cost_tracking_df["pump_id"] == pump_id]
    result = rows.to_dict("records")
    for r in result:
        r["source"] = "cost_tracking.csv"
    return result


def get_operating_schedule(pump_id: str) -> list[dict]:
    """Get recent operating schedule for a pump (last 30 entries)."""
    _load()
    rows = _operating_schedule_df[_operating_schedule_df["pump_id"] == pump_id].tail(30)
    result = rows.to_dict("records")
    for r in result:
        r["source"] = "operating_schedule.csv"
    return result


def get_health_history(pump_id: str) -> list[dict]:
    """Get daily health scores over the full dataset period for a pump."""
    _load()
    readings = _sensor_df[_sensor_df["pump_id"] == pump_id]
    if readings.empty:
        return []

    pump_meta = _pump_metadata_df[_pump_metadata_df["pump_id"] == pump_id].iloc[0]
    envelope = json.loads(pump_meta["operating_envelope_json"])

    readings = readings.set_index("timestamp").sort_index()
    daily = readings.resample("D").last().dropna(subset=["bearing_temp_c"])

    history = []
    for ts, row in daily.iterrows():
        day_data = readings.loc[:ts].tail(24)
        health = _compute_health(row, envelope, pump_id, day_data)
        history.append({
            "date": ts.strftime("%Y-%m-%d"),
            "score": health["score"],
            "status": health["status"],
            "flags": len(health["flags"]),
        })
    return history


def get_oem_manual_section(model: str, search_term: str = "") -> dict:
    """Read OEM manual for a pump model. Optionally search for a specific section."""
    ref_dir = f"{DATA_DIR}/reference_docs"
    model_to_file = {
        "Flowserve PVXM-3": "flowserve_pvxm3_manual.md",
        "KSB Etanorm 100-080": "ksb_etanorm_manual.md",
        "Sulzer CPT-50": "sulzer_cpt50_manual.md",
    }
    filename = model_to_file.get(model)
    if not filename:
        return {"error": f"Unknown model: {model}. Known: {list(model_to_file.keys())}"}

    filepath = f"{ref_dir}/{filename}"
    if not os.path.exists(filepath):
        return {"error": f"Manual not found at {filepath}"}

    with open(filepath) as f:
        content = f.read()

    if search_term:
        lines = content.split("\n")
        relevant = []
        for i, line in enumerate(lines):
            if search_term.lower() in line.lower():
                start = max(0, i - 2)
                end = min(len(lines), i + 15)
                relevant.append("\n".join(lines[start:end]))
        if relevant:
            return {
                "model": model,
                "search_term": search_term,
                "sections_found": len(relevant),
                "content": "\n\n---\n\n".join(relevant[:3]),
                "source": f"reference_docs/{filename}",
            }
        return {
            "model": model,
            "search_term": search_term,
            "sections_found": 0,
            "content": "No matching sections found.",
            "source": f"reference_docs/{filename}",
        }

    if len(content) > 4000:
        content = content[:4000] + "\n\n[... truncated — use search_term to find specific sections]"

    return {
        "model": model,
        "content": content,
        "source": f"reference_docs/{filename}",
    }


# ---------------------------------------------------------------------------
# Repair requirements — derived from pump attributes
# ---------------------------------------------------------------------------

def _get_repair_requirements(pump_row) -> dict:
    seal = str(pump_row["seal_type"])
    bearing = str(pump_row["bearing_type"])
    fluid = str(pump_row["service_fluid"]).lower()
    power_kw = float(pump_row["rated_power_kw"])
    criticality = int(pump_row["criticality_rating"])

    skills = []
    certifications = []
    effort_hrs = 4

    skills.append("Rotating equipment mechanic")
    if "double" in seal.lower():
        skills.append("Mechanical seal specialist")
        certifications.append("Seal system certification")
        effort_hrs += 4
    else:
        skills.append("Packing/seal technician")
        effort_hrs += 2

    if power_kw >= 37:
        skills.append("Electrical technician (HV)")
        certifications.append("High-voltage isolation permit")
        effort_hrs += 2

    if "crude" in fluid:
        certifications.append("H2S safety certification")
        certifications.append("Hot work permit")
        effort_hrs += 2
    elif "naphtha" in fluid or "kerosene" in fluid:
        certifications.append("Flammable fluids handling")
        effort_hrs += 1
    elif "diesel" in fluid or "fuel oil" in fluid:
        certifications.append("Flammable fluids handling")
        effort_hrs += 1

    skills.append("Vibration analyst (ISO 18436-2)")

    if criticality == 1:
        effort_level = "High"
        effort_hrs = int(effort_hrs * 1.3)
        certifications.append("Critical equipment sign-off")
    elif criticality == 2:
        effort_level = "Medium"
    else:
        effort_level = "Low"
        effort_hrs = int(effort_hrs * 0.8)

    return {
        "skills_required": skills,
        "certifications": certifications,
        "effort_level": effort_level,
        "estimated_repair_hrs": effort_hrs,
        "crew_size": 3 if criticality == 1 else 2,
    }


# ---------------------------------------------------------------------------
# Health scoring
# ---------------------------------------------------------------------------

def _compute_health(latest_row, envelope: dict, pump_id: str, pump_window=None) -> dict:
    """Compute a 0-100 health score from latest readings + short-term trends."""
    score = 100
    flags = []

    temp = float(latest_row["bearing_temp_c"])
    max_temp = envelope.get("max_bearing_temp_c", 95)
    if temp > max_temp:
        score -= 30
        flags.append(f"Bearing temp {temp:.1f}°C exceeds limit {max_temp}°C")
    elif temp > max_temp * 0.85:
        score -= 10
        flags.append(f"Bearing temp {temp:.1f}°C approaching limit {max_temp}°C")

    max_vib = envelope.get("max_vibration_mms", 7.1)
    for axis, col in [("X", "vibration_x_mms"), ("Y", "vibration_y_mms"), ("Axial", "vibration_axial_mms")]:
        v = float(latest_row[col])
        if v > max_vib:
            score -= 20
            flags.append(f"Vibration {axis} {v:.2f} mm/s exceeds limit {max_vib} mm/s")
        elif v > max_vib * 0.7:
            score -= 5
            flags.append(f"Vibration {axis} {v:.2f} mm/s elevated (limit {max_vib} mm/s)")
        elif v > 3.5:
            score -= 5
            flags.append(f"Vibration {axis} {v:.2f} mm/s above normal")

    flow = float(latest_row["flow_rate_m3hr"])
    min_flow = envelope.get("min_flow_m3hr", 0)
    max_flow = envelope.get("max_flow_m3hr", 999)
    if flow < min_flow or flow > max_flow:
        score -= 15
        flags.append(f"Flow {flow:.1f} m³/hr outside envelope [{min_flow}-{max_flow}]")

    if bool(latest_row["seal_leak_detected"]):
        score -= 25
        flags.append("Seal leak detected")

    suction = float(latest_row["suction_pressure_psi"])
    if suction < 15:
        score -= 20
        flags.append(f"Suction pressure {suction:.1f} psi — cavitation risk")
    elif suction < 25:
        score -= 10
        flags.append(f"Suction pressure {suction:.1f} psi — low, monitor for cavitation")
    elif suction < 35:
        score -= 5
        flags.append(f"Suction pressure {suction:.1f} psi — dropping")

    if pump_window is not None and len(pump_window) >= 12:
        recent = pump_window.tail(12)
        for col, name in [("bearing_temp_c", "Bearing temp"), ("vibration_axial_mms", "Axial vibration")]:
            vals = recent[col].astype(float)
            first_half = vals.iloc[:6].mean()
            second_half = vals.iloc[6:].mean()
            if col == "bearing_temp_c" and second_half > first_half + 3:
                score -= 10
                flags.append(f"{name} rising trend (+{second_half - first_half:.1f}°C in 1h)")
            elif col == "vibration_axial_mms" and second_half > first_half * 1.5 and second_half > 2.0:
                score -= 10
                flags.append(f"{name} rising trend ({first_half:.1f} → {second_half:.1f} mm/s)")

        suction_vals = recent["suction_pressure_psi"].astype(float)
        if suction_vals.iloc[-1] < suction_vals.iloc[0] * 0.8:
            score -= 10
            flags.append(f"Suction pressure dropping ({suction_vals.iloc[0]:.0f} → {suction_vals.iloc[-1]:.0f} psi)")

    label = str(latest_row.get("label", "normal"))
    if label == "pre_failure":
        score = min(score, 35)
        if "Pre-failure state detected" not in [f for f in flags]:
            flags.insert(0, "Pre-failure state detected in sensor data")
    elif label == "failure":
        score = min(score, 10)
        flags.insert(0, "ACTIVE FAILURE")

    score = max(0, score)

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "warning"
    else:
        status = "critical"

    return {"score": score, "status": status, "flags": flags}
