const SESSION_ID = "session_" + Date.now();
let fleetData = [];
let currentSnapshot = "";

// ---- Snapshots ----
async function loadSnapshots() {
    const res = await fetch("/api/snapshots");
    const snapshots = await res.json();
    const container = document.getElementById("snapshot-buttons");
    container.innerHTML = snapshots.map(s => `
        <button class="snapshot-btn ${s.ts === '' ? 'active' : ''}"
                onclick="setSnapshot('${s.ts}', this)"
                title="${s.ts || 'Current'}">${s.label}</button>
    `).join("");
}

async function setSnapshot(ts, btn) {
    currentSnapshot = ts;
    document.querySelectorAll(".snapshot-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    const tsDisplay = document.getElementById("timestamp-display");
    if (ts) {
        const d = new Date(ts);
        tsDisplay.textContent = `Viewing: ${d.toLocaleString("en-US", {month:"short",day:"numeric",year:"numeric",hour:"2-digit",minute:"2-digit"})}`;
        tsDisplay.style.display = "block";
    } else {
        tsDisplay.textContent = "Live — Feb 28, 2026";
        tsDisplay.style.display = "block";
    }

    await loadFleet();
}

// ---- Fleet Grid ----
async function loadFleet() {
    const url = currentSnapshot ? `/api/fleet?snapshot=${currentSnapshot}` : "/api/fleet";
    const res = await fetch(url);
    fleetData = await res.json();
    renderFleet();
}

function renderFleet() {
    const grid = document.getElementById("pump-grid");
    const stats = document.getElementById("fleet-stats");

    const counts = { healthy: 0, warning: 0, critical: 0 };
    fleetData.forEach(p => counts[p.health_status]++);

    let totalFailureCost = 0;
    let totalDowntime = 0;
    fleetData.forEach(p => {
        if (p.last_failure) {
            totalFailureCost += p.last_failure.cost_usd;
            totalDowntime += p.last_failure.downtime_hrs;
        }
    });

    stats.innerHTML = `
        <div class="stat-badge healthy">${counts.healthy} Healthy</div>
        <div class="stat-badge warning">${counts.warning} Warning</div>
        <div class="stat-badge critical">${counts.critical} Critical</div>
        ${totalFailureCost > 0 ? `<div class="stat-badge" style="background:rgba(239,68,68,0.08);color:#f87171;">$${(totalFailureCost/1000).toFixed(0)}K losses · ${totalDowntime.toFixed(0)}h down</div>` : ''}
    `;

    grid.innerHTML = fleetData.map(p => `
        <div class="pump-card ${p.health_status}" onclick="showPumpDetail('${p.pump_id}')">
            <div class="pump-card-header">
                <div>
                    <div class="pump-id">${p.pump_id}</div>
                    <div class="pump-model">${p.model}</div>
                </div>
                <span class="health-badge ${p.health_status}">${p.health_score}</span>
            </div>
            <div class="pump-sensors">
                <div class="sensor-row">
                    <span class="sensor-label">Bearing</span>
                    <span class="sensor-value">${p.bearing_temp_c}°C</span>
                </div>
                <div class="sensor-row">
                    <span class="sensor-label">Vib X</span>
                    <span class="sensor-value">${p.vibration_x} mm/s</span>
                </div>
                <div class="sensor-row">
                    <span class="sensor-label">Vib Y</span>
                    <span class="sensor-value">${p.vibration_y} mm/s</span>
                </div>
                <div class="sensor-row">
                    <span class="sensor-label">Vib Axial</span>
                    <span class="sensor-value">${p.vibration_axial} mm/s</span>
                </div>
                <div class="sensor-row">
                    <span class="sensor-label">Flow</span>
                    <span class="sensor-value">${p.flow_rate} m³/h</span>
                </div>
                <div class="sensor-row">
                    <span class="sensor-label">Motor</span>
                    <span class="sensor-value">${p.motor_current} A</span>
                </div>
            </div>
            <div class="pump-card-footer">
                <span><span class="criticality c${p.criticality}"></span>Criticality ${p.criticality}</span>
                ${p.last_failure ? `<span class="failure-tag">${p.last_failure.mode}</span>` : '<span>No failures</span>'}
            </div>
        </div>
    `).join("");
}

// ---- Pump Detail Overlay ----
async function showPumpDetail(pumpId) {
    const overlay = document.getElementById("pump-detail-overlay");
    const card = document.getElementById("pump-detail-card");
    const pump = fleetData.find(p => p.pump_id === pumpId);

    card.innerHTML = `
        <h2>${pumpId} — ${pump.model}</h2>
        <div class="detail-grid">
            <div class="detail-item">
                <div class="label">Health Score</div>
                <div class="value" style="color: var(--${pump.health_status === 'healthy' ? 'green' : pump.health_status === 'warning' ? 'yellow' : 'red'})">${pump.health_score}/100</div>
            </div>
            <div class="detail-item">
                <div class="label">Service Fluid</div>
                <div class="value">${pump.service_fluid}</div>
            </div>
            <div class="detail-item">
                <div class="label">Bearing Temp</div>
                <div class="value">${pump.bearing_temp_c}°C</div>
            </div>
            <div class="detail-item">
                <div class="label">Flow Rate</div>
                <div class="value">${pump.flow_rate} m³/h</div>
            </div>
            <div class="detail-item">
                <div class="label">Motor Current</div>
                <div class="value">${pump.motor_current} A</div>
            </div>
            <div class="detail-item">
                <div class="label">Seal Leak</div>
                <div class="value" style="color: ${pump.seal_leak ? 'var(--red)' : 'var(--green)'}">${pump.seal_leak ? 'DETECTED' : 'None'}</div>
            </div>
            <div class="detail-item">
                <div class="label">Vibration X / Y / Axial</div>
                <div class="value">${pump.vibration_x} / ${pump.vibration_y} / ${pump.vibration_axial} mm/s</div>
            </div>
            <div class="detail-item">
                <div class="label">Last Maintenance</div>
                <div class="value">${pump.last_maintenance}</div>
            </div>
        </div>
        ${pump.last_failure ? `
            <div style="background: var(--red-bg); padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                <strong style="color: var(--red);">Last Failure:</strong> ${pump.last_failure.mode}
                on ${pump.last_failure.date} — ${pump.last_failure.downtime_hrs}h downtime, $${pump.last_failure.cost_usd.toLocaleString()}
            </div>
        ` : ''}
        ${pump.health_flags.length > 0 ? `
            <div style="background: var(--yellow-bg); padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                <strong style="color: var(--yellow);">Flags:</strong>
                <ul style="margin-left: 18px; margin-top: 6px;">${pump.health_flags.map(f => `<li>${f}</li>`).join('')}</ul>
            </div>
        ` : ''}
        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
            <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'health')">Full health assessment</button>
            <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'failure')">Failure risk analysis</button>
            <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'maintenance')">Maintenance history</button>
            <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'manual')">OEM manual lookup</button>
        </div>
    `;

    overlay.classList.add("active");
}

function closePumpDetail() {
    document.getElementById("pump-detail-overlay").classList.remove("active");
}

function askAboutPump(pumpId, type) {
    closePumpDetail();
    const prompts = {
        health: `Give me a full health assessment for pump ${pumpId}. Check current sensor readings, trends over the last 24 hours, compare against vibration baselines, and flag anything concerning.`,
        failure: `Analyze pump ${pumpId}'s failure risk. Check its failure history, current sensor patterns against failure_mode_reference signatures, maintenance gaps, and predict the most likely next failure mode.`,
        maintenance: `Show me pump ${pumpId}'s complete maintenance history from both logs. When was it last serviced? Are there overdue maintenance items? What parts are available in inventory?`,
        manual: `Look up the OEM manual for pump ${pumpId}'s model. What are the manufacturer's vibration limits, recommended maintenance intervals, and troubleshooting steps for common issues?`,
    };
    const input = document.getElementById("chat-input");
    input.value = prompts[type] || prompts.health;
    input.focus();
    sendMessage();
}

document.addEventListener("keydown", e => {
    if (e.key === "Escape") closePumpDetail();
});

// ---- Chat ----
async function sendMessage() {
    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    addMessage("user", message);

    const thinkingEl = addMessage("thinking", "Analyzing data — this may take a moment...");
    const sendBtn = document.getElementById("send-btn");
    sendBtn.disabled = true;

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, session_id: SESSION_ID }),
        });
        const data = await res.json();

        thinkingEl.remove();
        addMessage("assistant", data.response, data.tools_used);
    } catch (err) {
        thinkingEl.remove();
        addMessage("assistant", "Error communicating with the server. Please try again.");
    }

    sendBtn.disabled = false;
    input.focus();
}

function addMessage(role, content, tools) {
    const container = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = `message ${role}`;

    let html = `<div class="message-content">${role === 'user' ? escapeHtml(content) : renderMarkdown(content)}</div>`;

    if (tools && tools.length > 0) {
        html += `<div class="tools-used">Data sources queried: ${tools.map(t => `<span class="tool-tag">${t.replace('get_', '').replace(/_/g, ' ')}</span>`).join(' ')}</div>`;
    }

    div.innerHTML = html;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

async function resetChat() {
    await fetch("/api/chat/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID }),
    });
    const container = document.getElementById("chat-messages");
    container.innerHTML = `
        <div class="message assistant">
            <div class="message-content">
                <p>Conversation reset. How can I help with the pump fleet?</p>
            </div>
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // headers
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        // horizontal rules
        .replace(/^---$/gm, '<hr>')
        // bold
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // italic
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // inline code
        .replace(/`(.+?)`/g, '<code>$1</code>')
        // tables
        .replace(/^\|(.+)\|$/gm, (match) => {
            const cells = match.split('|').filter(c => c.trim());
            if (cells.every(c => /^[\s-:]+$/.test(c))) return '';
            const tag = 'td';
            return '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
        })
        .replace(/(<tr>.*<\/tr>\n?)+/g, '<table>$&</table>')
        // bullet lists
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        // numbered lists
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        // paragraphs
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>')
        .replace(/<p><\/p>/g, '')
        .replace(/<p>(<h[23]>)/g, '$1')
        .replace(/(<\/h[23]>)<\/p>/g, '$1')
        .replace(/<p>(<hr>)<\/p>/g, '$1')
        .replace(/<p>(<table>)/g, '$1')
        .replace(/(<\/table>)<\/p>/g, '$1')
        .replace(/<p>(<ul>)/g, '$1')
        .replace(/(<\/ul>)<\/p>/g, '$1');
}

// ---- Init ----
document.addEventListener("DOMContentLoaded", () => {
    loadSnapshots();
    loadFleet();
    document.getElementById("timestamp-display").textContent = "Live — Feb 28, 2026";
});
