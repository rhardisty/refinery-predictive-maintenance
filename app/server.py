from flask import Flask, render_template, jsonify, request
import data_tools
import agent

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fleet")
def api_fleet():
    snapshot = request.args.get("snapshot", "")
    fleet = data_tools.get_fleet_overview(snapshot)
    return jsonify(fleet)


@app.route("/api/snapshots")
def api_snapshots():
    return jsonify([
        {"ts": "2025-09-25T23:00:00", "label": "P-01 bearing wear", "pump": "P-01"},
        {"ts": "2025-10-18T23:30:00", "label": "P-03 cavitation", "pump": "P-03"},
        {"ts": "2025-11-11T23:00:00", "label": "P-07 bearing wear", "pump": "P-07"},
        {"ts": "2025-12-04T23:00:00", "label": "P-05 seal failure", "pump": "P-05"},
        {"ts": "2025-12-27T12:00:00", "label": "P-10 misalignment", "pump": "P-10"},
        {"ts": "2026-01-18T23:00:00", "label": "P-02 impeller damage", "pump": "P-02"},
        {"ts": "2026-02-09T23:00:00", "label": "P-08 bearing wear", "pump": "P-08"},
        {"ts": "2026-02-22T23:00:00", "label": "P-11 seal failure", "pump": "P-11"},
        {"ts": "", "label": "Current (recovered)", "pump": ""},
    ])


@app.route("/api/pump/<pump_id>")
def api_pump(pump_id):
    return jsonify({
        "readings": data_tools.get_pump_latest_readings(pump_id),
        "metadata": data_tools.get_pump_metadata(pump_id),
        "failures": data_tools.get_failure_events(pump_id),
    })


@app.route("/api/pump/<pump_id>/health-history")
def api_health_history(pump_id):
    return jsonify(data_tools.get_health_history(pump_id))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json
    user_message = data.get("message", "")
    session_id = data.get("session_id", "default")

    result = agent.chat(user_message, session_id=session_id)

    return jsonify({
        "response": result["response"],
        "tools_used": [t["tool"] for t in result["tool_calls"]],
    })


@app.route("/api/chat/reset", methods=["POST"])
def api_chat_reset():
    data = request.json
    session_id = data.get("session_id", "default")
    agent.reset_session(session_id)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("Loading data...")
    data_tools._load()
    print("Data loaded. Starting Strands AgentCore server on port 3000...")
    app.run(host="0.0.0.0", port=3000, debug=False)
