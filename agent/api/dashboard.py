DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Conversion Engine</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f7f8f5;
        --panel: #ffffff;
        --ink: #1f2523;
        --muted: #5f6864;
        --accent: #9b3f2f;
        --accent-2: #2f6f57;
        --line: #d7ddd6;
        --shadow: rgba(31, 37, 35, 0.06);
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--ink);
        background: var(--bg);
      }

      main {
        width: min(1180px, calc(100% - 32px));
        margin: 0 auto;
        padding: 36px 0 60px;
      }

      .hero {
        display: grid;
        gap: 12px;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 12px 34px var(--shadow);
      }

      .eyebrow {
        margin: 0;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0;
        font-size: 0.8rem;
      }

      h1, h2, h3 {
        margin: 0;
        line-height: 1;
      }

      h1 {
        font-size: 3rem;
      }

      p {
        margin: 0;
        color: var(--muted);
        line-height: 1.6;
      }

      .top-grid,
      .bottom-grid {
        display: grid;
        gap: 18px;
        margin-top: 18px;
      }

      .top-grid {
        grid-template-columns: 1.15fr 0.85fr;
      }

      .bottom-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 22px;
        box-shadow: 0 12px 32px var(--shadow);
      }

      .stats {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }

      .stat {
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.72);
      }

      .stat strong {
        display: block;
        font-size: 2rem;
        margin-top: 8px;
      }

      form {
        display: grid;
        gap: 14px;
      }

      .field-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }

      label {
        display: grid;
        gap: 6px;
        font-size: 0.92rem;
        color: var(--ink);
      }

      input {
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 12px 14px;
        font: inherit;
        background: white;
      }

      button {
        border: 0;
        border-radius: 8px;
        padding: 12px 18px;
        font: inherit;
        color: white;
        background: linear-gradient(135deg, var(--accent) 0%, #a04422 100%);
        cursor: pointer;
      }

      button:disabled {
        opacity: 0.65;
        cursor: wait;
      }

      .hint {
        font-size: 0.92rem;
      }

      .stack {
        display: grid;
        gap: 12px;
      }

      .item {
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.72);
      }

      .item h3 {
        font-size: 1.1rem;
        margin-bottom: 8px;
      }

      .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 10px;
      }

      .pill {
        display: inline-flex;
        align-items: center;
        border-radius: 6px;
        padding: 6px 10px;
        background: rgba(28, 106, 102, 0.1);
        color: var(--accent-2);
        font-size: 0.85rem;
      }

      .muted-list {
        margin: 10px 0 0;
        padding-left: 18px;
        color: var(--muted);
      }

      pre {
        white-space: pre-wrap;
        background: #f6f8f5;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px;
        font-size: 0.92rem;
        line-height: 1.55;
      }

      .status {
        min-height: 24px;
        color: var(--accent-2);
        font-size: 0.95rem;
      }

      @media (max-width: 860px) {
        .top-grid,
        .bottom-grid,
        .field-grid {
          grid-template-columns: 1fr;
        }

        h1 {
          font-size: 2.2rem;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <p class="eyebrow">Tenacious Week 10</p>
        <h1>The Conversion Engine</h1>
        <p>Email-first prospect research, qualification, scheduling, CRM artifacts, and trace review.</p>
      </section>

      <section class="top-grid">
        <article class="panel">
          <h2>Create Prospect Brief</h2>
          <form id="prospect-form">
            <div class="field-grid">
              <label>
                Company Name
                <input name="company_name" required placeholder="Northstar Labs" />
              </label>
              <label>
                Company Domain
                <input name="company_domain" placeholder="northstarlabs.ai" />
              </label>
              <label>
                Contact Name
                <input name="contact_name" placeholder="Jordan Lee" />
              </label>
              <label>
                Contact Email
                <input name="contact_email" type="email" placeholder="jordan@northstarlabs.ai" />
              </label>
              <label>
                Contact Phone
                <input name="contact_phone" placeholder="+254700000000" />
              </label>
            </div>
            <button id="submit-button" type="submit">Run Full Toolchain</button>
            <div class="status" id="status"></div>
          </form>
        </article>

        <article class="panel">
          <h2>System State</h2>
          <div class="stats">
            <div class="stat">
              <span>Prospects</span>
              <strong id="prospect-count">0</strong>
            </div>
            <div class="stat">
              <span>Trace Events</span>
              <strong id="trace-count">0</strong>
            </div>
          </div>
          <div class="pill-row" style="margin-top: 16px;">
            <a class="pill" href="/docs" style="text-decoration:none;">API Docs</a>
            <a class="pill" href="/health" style="text-decoration:none;">Health Check</a>
            <a class="pill" href="/tools/status" style="text-decoration:none;">Tool Status JSON</a>
            <span class="pill">Email primary</span>
            <span class="pill">Outbound kill switch</span>
          </div>
        </article>
      </section>

      <section class="bottom-grid">
        <article class="panel stack">
          <h2>Latest Result</h2>
          <div id="latest-result">
            <p>No prospect brief has been generated in this browser session yet.</p>
          </div>
        </article>

        <article class="panel stack">
          <h2>Recent Prospects</h2>
          <div id="recent-prospects">
            <p>No saved prospects yet.</p>
          </div>
        </article>

        <article class="panel stack">
          <h2>Recent Traces</h2>
          <div id="recent-traces">
            <p>No trace events yet.</p>
          </div>
        </article>

        <article class="panel stack">
          <h2>Available Tools</h2>
          <div id="tool-statuses">
            <p>Loading tool status...</p>
          </div>
        </article>
      </section>
    </main>

    <script>
      const form = document.getElementById("prospect-form");
      const statusEl = document.getElementById("status");
      const submitButton = document.getElementById("submit-button");
      const latestResultEl = document.getElementById("latest-result");
      const recentProspectsEl = document.getElementById("recent-prospects");
      const recentTracesEl = document.getElementById("recent-traces");
      const toolStatusesEl = document.getElementById("tool-statuses");
      const prospectCountEl = document.getElementById("prospect-count");
      const traceCountEl = document.getElementById("trace-count");

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;");
      }

      function renderLatest(snapshot) {
        if (!snapshot) {
          latestResultEl.innerHTML = "<p>No prospect brief has been generated in this browser session yet.</p>";
          return;
        }

        const signals = snapshot.hiring_signal_brief.signals
          .map((signal) => `<li>${escapeHtml(signal.name)}: ${escapeHtml(signal.summary)}</li>`)
          .join("");
        const guardrails = snapshot.hiring_signal_brief.do_not_claim
          .map((item) => `<li>${escapeHtml(item)}</li>`)
          .join("");
        const peers = snapshot.competitor_gap_brief.peer_companies
          .map((item) => `<span class="pill">${escapeHtml(item)}</span>`)
          .join("");
        const toolResults = (snapshot.toolchain_report?.results || [])
          .map((result) => `
            <li>${escapeHtml(result.name)}: ${escapeHtml(result.status)} (${escapeHtml(result.mode)})</li>
          `)
          .join("");

        latestResultEl.innerHTML = `
          <div class="item">
            <h3>${escapeHtml(snapshot.prospect.company_name)}</h3>
            <p>${escapeHtml(snapshot.hiring_signal_brief.summary)}</p>
            <div class="pill-row">
              <span class="pill">Segment: ${escapeHtml(snapshot.prospect.primary_segment)}</span>
              <span class="pill">Confidence: ${escapeHtml(Math.round((snapshot.prospect.segment_confidence || 0) * 100))}%</span>
              <span class="pill">AI maturity: ${escapeHtml(snapshot.prospect.ai_maturity_score)}</span>
              <span class="pill">Trace: ${escapeHtml(snapshot.trace_id || "pending")}</span>
            </div>
          </div>
          <div class="item">
            <h3>Signal Brief</h3>
            <p>${escapeHtml(snapshot.hiring_signal_brief.recommended_pitch_angle)}</p>
            <ul class="muted-list">${signals}</ul>
          </div>
          <div class="item">
            <h3>Bench Match</h3>
            <p>${escapeHtml(snapshot.hiring_signal_brief.bench_match?.recommendation || "")}</p>
            <div class="pill-row">
              ${(snapshot.hiring_signal_brief.bench_match?.required_stacks || []).map((stack) => `<span class="pill">${escapeHtml(stack)}: ${escapeHtml(snapshot.hiring_signal_brief.bench_match.available_capacity?.[stack] ?? 0)}</span>`).join("")}
            </div>
          </div>
          <div class="item">
            <h3>Competitor Gap</h3>
            <p>${escapeHtml(snapshot.competitor_gap_brief.safe_gap_framing)}</p>
            <div class="pill-row">${peers}</div>
          </div>
          <div class="item">
            <h3>Initial Outreach Draft</h3>
            <pre>${escapeHtml(snapshot.initial_decision?.reply_draft || "")}</pre>
          </div>
          <div class="item">
            <h3>Guardrails</h3>
            <ul class="muted-list">${guardrails}</ul>
          </div>
          <div class="item">
            <h3>Toolchain Results</h3>
            <ul class="muted-list">${toolResults || "<li>No toolchain run recorded yet.</li>"}</ul>
          </div>
        `;
      }

      function renderProspects(snapshots) {
        if (!snapshots.length) {
          recentProspectsEl.innerHTML = "<p>No saved prospects yet.</p>";
          return;
        }
        recentProspectsEl.innerHTML = snapshots.map((snapshot) => `
          <div class="item">
            <h3>${escapeHtml(snapshot.prospect.company_name)}</h3>
            <p>${escapeHtml(snapshot.hiring_signal_brief.summary)}</p>
            <div class="pill-row">
              <span class="pill">${escapeHtml(snapshot.prospect.primary_segment)}</span>
              <span class="pill">${escapeHtml(Math.round((snapshot.prospect.segment_confidence || 0) * 100))}% confidence</span>
              <span class="pill">AI ${escapeHtml(snapshot.prospect.ai_maturity_score)}</span>
            </div>
          </div>
        `).join("");
      }

      function renderTraces(traces) {
        if (!traces.length) {
          recentTracesEl.innerHTML = "<p>No trace events yet.</p>";
          return;
        }
        recentTracesEl.innerHTML = traces.map((trace) => `
          <div class="item">
            <h3>${escapeHtml(trace.event_type)}</h3>
            <p>${escapeHtml(trace.company_name || "Unknown company")}</p>
            <div class="pill-row">
              <span class="pill">${escapeHtml(trace.trace_id)}</span>
              <span class="pill">${escapeHtml(trace.timestamp)}</span>
            </div>
          </div>
        `).join("");
      }

      function renderToolStatuses(statuses) {
        if (!statuses.length) {
          toolStatusesEl.innerHTML = "<p>No tool status data yet.</p>";
          return;
        }
        toolStatusesEl.innerHTML = statuses.map((tool) => `
          <div class="item">
            <h3>${escapeHtml(tool.label)}</h3>
            <p>${escapeHtml(tool.details)}</p>
            <div class="pill-row">
              <span class="pill">${escapeHtml(tool.name)}</span>
              <span class="pill">${escapeHtml(tool.mode)}</span>
              <span class="pill">${tool.configured ? "configured" : "not configured"}</span>
            </div>
          </div>
        `).join("");
      }

      async function loadState() {
        const response = await fetch("/dashboard/state");
        const state = await response.json();
        prospectCountEl.textContent = state.total_prospects;
        traceCountEl.textContent = state.total_traces;
        renderProspects(state.recent_snapshots);
        renderTraces(state.recent_traces);
        renderToolStatuses(state.tool_statuses || []);
      }

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        submitButton.disabled = true;
        statusEl.textContent = "Running the full development-mode toolchain...";
        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());

        try {
          const response = await fetch("/pipeline/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });

          if (!response.ok) {
            throw new Error("The backend could not generate the brief.");
          }

          const snapshot = await response.json();
          renderLatest(snapshot);
          await loadState();
          statusEl.textContent = "Toolchain run completed and saved.";
          form.reset();
        } catch (error) {
          statusEl.textContent = error.message;
        } finally {
          submitButton.disabled = false;
        }
      });

      loadState();
    </script>
  </body>
</html>
"""
