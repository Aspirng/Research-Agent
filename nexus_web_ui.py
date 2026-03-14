#!/usr/bin/env python3
"""
Nexus Research Agent — Web UI
File-based job store so multiple gunicorn workers share state correctly.
"""

import os
import json
import uuid
import tempfile
import threading
from datetime import datetime

from flask import Flask, request, send_file, jsonify

import research_agent as ra

app = Flask(__name__)

# All jobs stored in /tmp/nexus_jobs/ as JSON files — visible to all workers
JOBS_DIR = "/tmp/nexus_jobs"
os.makedirs(JOBS_DIR, exist_ok=True)


# ── Job helpers ───────────────────────────────────────────────────────────────

def job_path(job_id):
    return os.path.join(JOBS_DIR, f"{job_id}.json")

def write_job(job_id, data):
    with open(job_path(job_id), "w") as f:
        json.dump(data, f)

def read_job(job_id):
    p = job_path(job_id)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


# ── HTML ──────────────────────────────────────────────────────────────────────

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Nexus Research Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --ink:     #0a0a0f;
      --paper:   #f5f2eb;
      --cream:   #ede9df;
      --accent:  #c8410b;
      --accent2: #1a4a8a;
      --muted:   #7a7570;
      --border:  #d4cfc6;
      --success: #1a6e3c;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'DM Sans', sans-serif;
      background: var(--paper);
      color: var(--ink);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px 16px;
      background-image:
        radial-gradient(ellipse at 10% 20%, rgba(200,65,11,0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 90% 80%, rgba(26,74,138,0.06) 0%, transparent 50%);
    }
    .container { width: 100%; max-width: 680px; }
    .masthead { display: flex; align-items: baseline; gap: 14px; margin-bottom: 40px; }
    .masthead-logo { font-family: 'DM Serif Display', serif; font-size: 2.6rem; color: var(--ink); letter-spacing: -1px; line-height: 1; }
    .masthead-logo span { color: var(--accent); }
    .masthead-rule { flex: 1; height: 1px; background: var(--border); }
    .masthead-tag { font-size: 0.72rem; font-family: 'DM Mono', monospace; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase; }
    .card { background: #faf8f4; border: 1px solid var(--border); border-radius: 3px; padding: 36px; box-shadow: 4px 4px 0 var(--border), 8px 8px 0 rgba(0,0,0,0.04); }
    .card-eyebrow { font-family: 'DM Mono', monospace; font-size: 0.7rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent); margin-bottom: 8px; }
    .card-title { font-family: 'DM Serif Display', serif; font-size: 1.5rem; color: var(--ink); margin-bottom: 6px; line-height: 1.3; }
    .card-sub { font-size: 0.88rem; color: var(--muted); margin-bottom: 28px; line-height: 1.6; }
    .field { margin-bottom: 18px; }
    .field-label { display: block; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--ink); margin-bottom: 7px; }
    input { width: 100%; padding: 11px 14px; font-size: 0.95rem; font-family: 'DM Sans', sans-serif; background: var(--paper); border: 1px solid var(--border); border-radius: 2px; color: var(--ink); outline: none; transition: border-color 0.15s, box-shadow 0.15s; }
    input:focus { border-color: var(--accent2); box-shadow: 0 0 0 3px rgba(26,74,138,0.1); }
    input::placeholder { color: #b0ab9f; }
    .field-hint { font-size: 0.75rem; color: var(--muted); margin-top: 5px; font-family: 'DM Mono', monospace; }
    .btn-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 26px; flex-wrap: wrap; }
    .btn { display: inline-flex; align-items: center; gap: 10px; padding: 12px 28px; font-size: 0.88rem; font-weight: 600; font-family: 'DM Sans', sans-serif; letter-spacing: 0.03em; background: var(--ink); color: var(--paper); border: none; border-radius: 2px; cursor: pointer; transition: background 0.15s, transform 0.1s; text-decoration: none; }
    .btn:hover { background: #1e1e2a; transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }
    .btn.accent { background: var(--accent); }
    .btn.accent:hover { background: #a83409; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    .btn-meta { font-size: 0.75rem; color: var(--muted); line-height: 1.6; font-family: 'DM Mono', monospace; }
    .btn-meta strong { color: var(--ink); font-weight: 500; }
    #status-area { margin-top: 28px; display: none; }
    .status-box { border: 1px solid var(--border); border-radius: 2px; padding: 20px 22px; background: var(--cream); }
    .status-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
    .spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .status-label { font-family: 'DM Mono', monospace; font-size: 0.8rem; color: var(--ink); font-weight: 500; }
    .progress-track { height: 3px; background: var(--border); border-radius: 99px; overflow: hidden; }
    .progress-bar { height: 100%; background: var(--accent); border-radius: 99px; transition: width 0.6s ease; width: 5%; }
    .status-note { font-size: 0.75rem; color: var(--muted); margin-top: 10px; font-family: 'DM Mono', monospace; }
    .done-box { border: 1px solid #b8dfc8; border-radius: 2px; padding: 20px 22px; background: #f0faf4; display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
    .done-text { font-size: 0.88rem; color: var(--success); font-weight: 600; }
    .done-sub { font-size: 0.75rem; color: var(--muted); margin-top: 3px; font-family: 'DM Mono', monospace; }
    .error-box { border: 1px solid #f5c6b8; border-radius: 2px; padding: 16px 20px; background: #fff5f2; font-size: 0.85rem; color: var(--accent); }
    .divider { border: none; border-top: 1px solid var(--border); margin: 28px 0; }
    .footer-note { font-size: 0.72rem; color: var(--muted); font-family: 'DM Mono', monospace; text-align: center; margin-top: 24px; line-height: 1.8; }
  </style>
</head>
<body>
  <div class="container">
    <div class="masthead">
      <div class="masthead-logo">Ne<span>x</span>us</div>
      <div class="masthead-rule"></div>
      <div class="masthead-tag">Research Agent · Claude AI</div>
    </div>
    <div class="card">
      <div class="card-eyebrow">Instant Research PDF</div>
      <div class="card-title">Turn any topic into a verified research report</div>
      <div class="card-sub">Searches the web in real time, cites every claim, exports a clean PDF in under 60 seconds.</div>
      <div class="field">
        <label class="field-label" for="api_key">Anthropic API Key</label>
        <input type="password" id="api_key" placeholder="sk-ant-..." autocomplete="off"/>
        <div class="field-hint">Used only for this request. Never stored.</div>
      </div>
      <div class="field">
        <label class="field-label" for="topic">Research Topic</label>
        <input type="text" id="topic" placeholder="e.g. Impact of AI on software engineering jobs" autocomplete="off"/>
        <div class="field-hint">Be specific for better results.</div>
      </div>
      <div class="btn-row">
        <button class="btn accent" id="submit-btn" onclick="startResearch()">
          <span>Generate PDF</span>
          <span>&#x2197;</span>
        </button>
        <div class="btn-meta">
          <strong>Output:</strong> 4-6 section research report<br>
          Powered by Claude Sonnet + live web search
        </div>
      </div>
      <div id="status-area">
        <hr class="divider">
        <div id="status-content"></div>
      </div>
    </div>
    <div class="footer-note">
      Your API key goes directly to Anthropic. This app never stores it.<br>
      Each report costs ~$0.10-0.20 from your Anthropic account.
    </div>
  </div>
  <script>
    let pollInterval = null;

    function startResearch() {
      const apiKey = document.getElementById('api_key').value.trim();
      const topic  = document.getElementById('topic').value.trim();
      if (!apiKey.startsWith('sk-')) { showError('API key should start with sk-'); return; }
      if (!topic) { showError('Please enter a research topic.'); return; }
      document.getElementById('submit-btn').disabled = true;
      showProcessing('Starting research...');
      fetch('/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, topic: topic })
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) { showError(data.error); resetBtn(); return; }
        pollJob(data.job_id);
      })
      .catch(e => { showError('Network error: ' + e); resetBtn(); });
    }

    function pollJob(jobId) {
      let elapsed = 0;
      pollInterval = setInterval(() => {
        elapsed += 3;
        updateProgress(Math.min(90, 5 + elapsed * 1.4), getStatusMsg(elapsed));
        fetch('/status/' + jobId)
        .then(r => r.json())
        .then(data => {
          if (data.status === 'done') { clearInterval(pollInterval); showDone(jobId, data.topic); }
          else if (data.status === 'error') { clearInterval(pollInterval); showError(data.error); resetBtn(); }
        });
      }, 3000);
    }

    function getStatusMsg(s) {
      if (s < 10) return 'Searching the web...';
      if (s < 25) return 'Analysing sources...';
      if (s < 40) return 'Writing report...';
      return 'Building PDF...';
    }

    function showProcessing(msg) {
      document.getElementById('status-area').style.display = 'block';
      document.getElementById('status-content').innerHTML = `
        <div class="status-box">
          <div class="status-header">
            <div class="spinner"></div>
            <div class="status-label" id="status-label">${msg}</div>
          </div>
          <div class="progress-track"><div class="progress-bar" id="progress-bar" style="width:5%"></div></div>
          <div class="status-note">This usually takes 30-60 seconds. Hang tight.</div>
        </div>`;
    }

    function updateProgress(pct, msg) {
      const bar = document.getElementById('progress-bar');
      const lbl = document.getElementById('status-label');
      if (bar) bar.style.width = pct + '%';
      if (lbl) lbl.textContent = msg;
    }

    function showDone(jobId, topic) {
      document.getElementById('status-content').innerHTML = `
        <div class="done-box">
          <div>
            <div class="done-text">Report ready</div>
            <div class="done-sub">${topic}</div>
          </div>
          <a class="btn" href="/download/${jobId}">Download PDF</a>
        </div>`;
      resetBtn();
    }

    function showError(msg) {
      document.getElementById('status-area').style.display = 'block';
      document.getElementById('status-content').innerHTML = `<div class="error-box">&#9888; ${msg}</div>`;
    }

    function resetBtn() { document.getElementById('submit-btn').disabled = false; }
  </script>
</body>
</html>
"""


# ── Background worker ─────────────────────────────────────────────────────────

def run_research(job_id, api_key, topic):
    original_key = None
    try:
        original_key = ra.API_KEY
        ra.API_KEY = api_key

        report = ra.research(topic)

        import re
        safe = re.sub(r"[^\w\s-]", "", topic).strip().replace(" ", "_")[:50]
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp  = tempfile.mkdtemp(prefix="nexus_")
        path = os.path.join(tmp, f"nexus_{safe}_{ts}.pdf")

        ra.ReportPDF(topic, report, path).build()
        write_job(job_id, {"status": "done", "path": path, "topic": topic})

    except Exception as exc:
        write_job(job_id, {"status": "error", "error": str(exc), "topic": topic})

    finally:
        if original_key is not None:
            try: 
                ra.API_KEY = original_key
            except Exception:
                pass


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return PAGE


@app.route("/start", methods=["POST"])
def start():
    data    = request.get_json(force=True)
    api_key = (data.get("api_key") or "").strip()
    topic   = (data.get("topic")   or "").strip()

    if not api_key.startswith("sk-"):
        return jsonify({"error": "API key should start with sk-"})
    if not topic:
        return jsonify({"error": "Please enter a topic."})

    job_id = str(uuid.uuid4())
    write_job(job_id, {"status": "running", "topic": topic})

    t = threading.Thread(target=run_research, args=(job_id, api_key, topic), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = read_job(job_id)
    if not job:
        return jsonify({"status": "error", "error": "Job not found."})
    return jsonify(job)


@app.route("/download/<job_id>")
def download(job_id):
    job = read_job(job_id)
    if not job or job.get("status") != "done":
        return "File not ready or not found.", 404
    path = job["path"]
    if not os.path.exists(path):
        return "File missing from server.", 404
    return send_file(
        path,
        as_attachment=True,
        download_name=os.path.basename(path),
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    port  = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").strip() == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
