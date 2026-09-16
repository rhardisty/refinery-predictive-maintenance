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

    const sections = [
        { level: 1, label: "Critical", desc: "Production-critical pumps" },
        { level: 2, label: "Important", desc: "High-impact pumps" },
        { level: 3, label: "Standard", desc: "Standard-duty pumps" },
    ];

    const renderCard = p => `
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
        </div>`;

    grid.innerHTML = sections.map(s => {
        const pumps = fleetData.filter(p => p.criticality === s.level);
        if (pumps.length === 0) return '';
        return `
            <div class="criticality-section-header c${s.level}">
                <span class="criticality c${s.level}"></span>
                Criticality ${s.level} — ${s.label}
                <span class="section-desc">${s.desc} (${pumps.length})</span>
            </div>
            ${pumps.map(renderCard).join("")}`;
    }).join("");
}

// ---- Pump Detail Overlay ----
async function showPumpDetail(pumpId) {
    const overlay = document.getElementById("pump-detail-overlay");
    const card = document.getElementById("pump-detail-card");
    const pump = fleetData.find(p => p.pump_id === pumpId);

    card.innerHTML = `
        <h2>${pumpId} — ${pump.model}</h2>
        <div class="detail-tabs">
            <button class="detail-tab active" onclick="switchDetailTab(this, 'overview')">Overview</button>
            <button class="detail-tab" onclick="switchDetailTab(this, 'health-history')">Health History</button>
        </div>
        <div class="detail-tab-content" id="tab-overview">
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
            ${pump.repair_requirements ? `
            <div class="repair-requirements">
                <div class="repair-header">
                    <strong>Repair Requirements</strong>
                    <span class="effort-badge effort-${pump.repair_requirements.effort_level.toLowerCase()}">${pump.repair_requirements.effort_level} Effort · ~${pump.repair_requirements.estimated_repair_hrs}h · ${pump.repair_requirements.crew_size}-person crew</span>
                </div>
                <div class="repair-details">
                    <div class="repair-col">
                        <div class="repair-label">Skills Needed</div>
                        <ul>${pump.repair_requirements.skills_required.map(s => `<li>${s}</li>`).join('')}</ul>
                    </div>
                    <div class="repair-col">
                        <div class="repair-label">Certifications / Permits</div>
                        <ul>${pump.repair_requirements.certifications.map(c => `<li>${c}</li>`).join('')}</ul>
                    </div>
                </div>
            </div>
            ` : ''}
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
                <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'health')">Full health assessment</button>
                <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'failure')">Failure risk analysis</button>
                <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'maintenance')">Maintenance history</button>
                <button class="quick-ask-btn" onclick="askAboutPump('${pumpId}', 'manual')">OEM manual lookup</button>
            </div>
        </div>
        <div class="detail-tab-content" id="tab-health-history" style="display:none;">
            <div class="health-chart-loading">Loading health history...</div>
            <div class="health-chart-container" id="health-chart"></div>
        </div>
    `;

    overlay.classList.add("active");
    loadHealthHistory(pumpId);
}

function switchDetailTab(btn, tabId) {
    btn.parentElement.querySelectorAll(".detail-tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    btn.closest(".pump-detail-card").querySelectorAll(".detail-tab-content").forEach(c => c.style.display = "none");
    document.getElementById("tab-" + tabId).style.display = "block";
}

async function loadHealthHistory(pumpId) {
    const container = document.getElementById("health-chart");
    const loading = container.parentElement.querySelector(".health-chart-loading");
    try {
        const res = await fetch(`/api/pump/${pumpId}/health-history`);
        const data = await res.json();
        if (loading) loading.style.display = "none";
        renderHealthChart(container, data);
    } catch (err) {
        if (loading) loading.textContent = "Failed to load health history.";
    }
}

function renderHealthChart(container, data) {
    if (!data || data.length === 0) {
        container.innerHTML = '<div style="color:var(--text-dim);padding:20px;">No history available.</div>';
        return;
    }

    const W = 540, H = 200, PAD_L = 40, PAD_R = 16, PAD_T = 16, PAD_B = 40;
    const chartW = W - PAD_L - PAD_R;
    const chartH = H - PAD_T - PAD_B;

    const x = (i) => PAD_L + (i / (data.length - 1)) * chartW;
    const y = (score) => PAD_T + chartH - (score / 100) * chartH;

    const colorForScore = (s) => s >= 80 ? '#22c55e' : s >= 50 ? '#eab308' : '#ef4444';

    // Zone backgrounds
    let zones = `
        <rect x="${PAD_L}" y="${y(100)}" width="${chartW}" height="${y(80) - y(100)}" fill="rgba(34,197,94,0.06)"/>
        <rect x="${PAD_L}" y="${y(80)}" width="${chartW}" height="${y(50) - y(80)}" fill="rgba(234,179,8,0.06)"/>
        <rect x="${PAD_L}" y="${y(50)}" width="${chartW}" height="${y(0) - y(50)}" fill="rgba(239,68,68,0.06)"/>
    `;

    // Zone threshold lines
    let thresholds = `
        <line x1="${PAD_L}" y1="${y(80)}" x2="${W - PAD_R}" y2="${y(80)}" stroke="#eab308" stroke-width="0.5" stroke-dasharray="4,4" opacity="0.5"/>
        <line x1="${PAD_L}" y1="${y(50)}" x2="${W - PAD_R}" y2="${y(50)}" stroke="#ef4444" stroke-width="0.5" stroke-dasharray="4,4" opacity="0.5"/>
    `;

    // Y-axis labels
    let yLabels = [0, 25, 50, 80, 100].map(v =>
        `<text x="${PAD_L - 6}" y="${y(v) + 4}" fill="#8899aa" font-size="10" text-anchor="end">${v}</text>`
    ).join('');

    // X-axis labels (show ~6 dates)
    const step = Math.max(1, Math.floor(data.length / 6));
    let xLabels = data.filter((_, i) => i % step === 0 || i === data.length - 1).map(d => {
        const i = data.indexOf(d);
        const label = d.date.slice(5); // MM-DD
        return `<text x="${x(i)}" y="${H - 6}" fill="#8899aa" font-size="10" text-anchor="middle">${label}</text>`;
    }).join('');

    // Line path with color segments
    let segments = '';
    for (let i = 1; i < data.length; i++) {
        const color = colorForScore(Math.min(data[i-1].score, data[i].score));
        segments += `<line x1="${x(i-1)}" y1="${y(data[i-1].score)}" x2="${x(i)}" y2="${y(data[i].score)}" stroke="${color}" stroke-width="2"/>`;
    }

    // Dots for low-score days
    let dots = data.map((d, i) => {
        if (d.score < 80) {
            return `<circle cx="${x(i)}" cy="${y(d.score)}" r="3" fill="${colorForScore(d.score)}" stroke="${colorForScore(d.score)}" stroke-width="1">
                <title>${d.date}: ${d.score}/100 (${d.status})</title>
            </circle>`;
        }
        return '';
    }).join('');

    // Hover dots (invisible, larger hit area)
    let hoverDots = data.map((d, i) =>
        `<circle cx="${x(i)}" cy="${y(d.score)}" r="6" fill="transparent" stroke="transparent">
            <title>${d.date}: ${d.score}/100 (${d.status}, ${d.flags} flag${d.flags !== 1 ? 's' : ''})</title>
        </circle>`
    ).join('');

    // Stats summary
    const minScore = Math.min(...data.map(d => d.score));
    const avgScore = Math.round(data.reduce((s, d) => s + d.score, 0) / data.length);
    const critDays = data.filter(d => d.status === 'critical').length;
    const warnDays = data.filter(d => d.status === 'warning').length;

    container.innerHTML = `
        <div class="health-chart-stats">
            <span>Min: <strong style="color:${colorForScore(minScore)}">${minScore}</strong></span>
            <span>Avg: <strong style="color:${colorForScore(avgScore)}">${avgScore}</strong></span>
            <span>${critDays}d critical</span>
            <span>${warnDays}d warning</span>
            <span>${data.length}d total</span>
        </div>
        <svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet">
            ${zones}${thresholds}${yLabels}${xLabels}${segments}${dots}${hoverDots}
        </svg>
        <div class="health-chart-legend">
            <span><span class="legend-dot" style="background:#22c55e"></span>Healthy (80-100)</span>
            <span><span class="legend-dot" style="background:#eab308"></span>Warning (50-79)</span>
            <span><span class="legend-dot" style="background:#ef4444"></span>Critical (0-49)</span>
        </div>
    `;
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
