#!/usr/bin/env python3
"""
Minimal web UI for Nexus Research Agent.

Run:
    pip install flask anthropic reportlab
    python nexus_web_ui.py

Then open http://127.0.0.1:5000 in your browser.
"""

import os
import tempfile
from datetime import datetime

from flask import Flask, request, send_file, redirect, url_for

import nexus_research as nexus


app = Flask(__name__)


def _default_depth() -> str:
    """
    Use the recommended "Standard" depth (5 lessons) for the web UI.
    """
    return "2"


def _render_page(message: str = "", download_url: str | None = None):
    """
    Simple in-file template renderer using f-strings.
    """
    # Basic HTML with a modern, minimal, responsive design.
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Nexus Research Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #050816;
      --bg-soft: #0f172a;
      --card-bg: #020617;
      --accent: #7c6dfa;
      --accent-soft: #4338ca;
      --accent-alt: #38bdf8;
      --border-subtle: #1e293b;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --danger: #f97373;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(124, 109, 250, 0.16), transparent 55%),
        radial-gradient(circle at bottom right, rgba(56, 189, 248, 0.12), transparent 55%),
        var(--bg);
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .shell {{
      width: 100%;
      max-width: 760px;
      background: radial-gradient(circle at top left, rgba(124,109,250,0.32), transparent 40%),
                  radial-gradient(circle at bottom right, rgba(15,23,42,0.9), rgba(15,23,42,0.98));
      border-radius: 24px;
      padding: 1px;
      box-shadow:
        0 20px 40px rgba(15,23,42,0.7),
        0 0 0 1px rgba(148,163,184,0.12);
    }}
    .card {{
      border-radius: 23px;
      background: linear-gradient(135deg, rgba(15,23,42,0.96), rgba(2,6,23,0.98));
      padding: 28px 28px 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }}
    .header {{
      display: flex;
      flex-wrap: wrap;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
    }}
    .title-block {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .logo-pill {{
      width: 40px;
      height: 40px;
      border-radius: 16px;
      background: radial-gradient(circle at 30% 20%, #e5e7eb, transparent 55%),
                  linear-gradient(145deg, #6366f1, #a855f7);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 700;
      font-size: 18px;
      box-shadow: 0 10px 25px rgba(67,56,202,0.65);
    }}
    .title {{
      font-size: 1.1rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #a5b4fc;
    }}
    .subtitle {{
      font-size: 0.92rem;
      color: var(--muted);
      margin-top: 2px;
    }}
    .tag {{
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid rgba(148, 163, 184, 0.35);
      font-size: 0.78rem;
      color: #c4b5fd;
      background: radial-gradient(circle at top left, rgba(124, 109, 250, 0.35), transparent 55%);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .tag-dot {{
      width: 6px;
      height: 6px;
      border-radius: 999px;
      background: #4ade80;
      box-shadow: 0 0 0 4px rgba(74, 222, 128, 0.25);
    }}
    form {{
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-top: 8px;
    }}
    .field-row {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.8fr);
      gap: 14px;
    }}
    @media (max-width: 720px) {{
      .field-row {{
        grid-template-columns: minmax(0, 1fr);
      }}
    }}
    .field {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .field-label {{
      font-size: 0.85rem;
      font-weight: 500;
      color: #e5e7eb;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }}
    .field-hint {{
      font-size: 0.78rem;
      color: var(--muted);
    }}
    .input-shell {{
      position: relative;
      border-radius: 14px;
      background: radial-gradient(circle at top left, rgba(148,163,184,0.18), transparent 45%),
                  rgba(15,23,42,0.92);
      border: 1px solid rgba(148, 163, 184, 0.3);
      padding: 9px 11px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .input-shell:focus-within {{
      border-color: rgba(129, 140, 248, 0.9);
      box-shadow: 0 0 0 1px rgba(129,140,248,0.5);
    }}
    .input-shell span.icon {{
      font-size: 0.9rem;
      color: var(--muted);
    }}
    input {{
      border: none;
      outline: none;
      background: transparent;
      color: var(--text);
      width: 100%;
      font-size: 0.9rem;
    }}
    input::placeholder {{
      color: #6b7280;
    }}
    .actions-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 4px;
      flex-wrap: wrap;
    }}
    .submit-btn {{
      position: relative;
      border: none;
      border-radius: 999px;
      padding: 10px 22px;
      font-size: 0.9rem;
      font-weight: 500;
      cursor: pointer;
      color: #f9fafb;
      background: linear-gradient(135deg, var(--accent), var(--accent-alt));
      display: inline-flex;
      align-items: center;
      gap: 8px;
      box-shadow:
        0 14px 30px rgba(15, 23, 42, 0.9),
        0 0 0 1px rgba(129,140,248,0.4);
      transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
    }}
    .submit-btn span.chevron {{
      transform: translateX(0);
      transition: transform 0.12s ease;
      font-size: 0.9rem;
    }}
    .submit-btn:hover {{
      transform: translateY(-1px);
      filter: brightness(1.06);
      box-shadow:
        0 18px 45px rgba(15, 23, 42, 0.95),
        0 0 0 1px rgba(129,140,248,0.7);
    }}
    .submit-btn:hover span.chevron {{
      transform: translateX(2px);
    }}
    .submit-btn:active {{
      transform: translateY(0);
      box-shadow:
        0 8px 20px rgba(15, 23, 42, 0.9),
        0 0 0 1px rgba(129,140,248,0.6);
    }}
    .meta {{
      display: flex;
      flex-direction: column;
      gap: 3px;
      font-size: 0.8rem;
      color: var(--muted);
    }}
    .meta strong {{
      color: #e5e7eb;
      font-weight: 500;
    }}
    .status {{
      margin-top: 10px;
      font-size: 0.85rem;
      color: {"#4ade80" if download_url else ("var(--danger)" if message.startswith("Error") else "var(--muted)")};
    }}
    .status a {{
      color: #a5b4fc;
      text-decoration: none;
      border-bottom: 1px dashed rgba(165, 180, 252, 0.7);
    }}
    .status a:hover {{
      color: #c4b5fd;
    }}
  </style>
</head>
<body>
  <div class="shell">
    <div class="card">
      <div class="header">
        <div class="title-block">
          <div class="logo-pill">N</div>
          <div>
            <div class="title">Nexus Research Agent</div>
            <div class="subtitle">Turn any topic into a structured, source-backed course PDF.</div>
          </div>
        </div>
        <div class="tag">
          <span class="tag-dot"></span>
          <span>Live web research · Claude</span>
        </div>
      </div>

      <form method="POST" action="{url_for('index')}">
        <div class="field-row">
          <div class="field">
            <div class="field-label">
              <span>Anthropic API key</span>
            </div>
            <div class="input-shell">
              <span class="icon">🔑</span>
              <input
                type="password"
                name="api_key"
                autocomplete="off"
                required
                placeholder="sk-..."
              />
            </div>
            <div class="field-hint">
              Key is used only locally on this machine and never stored.
            </div>
          </div>

          <div class="field">
            <div class="field-label">
              <span>Topic to research</span>
            </div>
            <div class="input-shell">
              <span class="icon">📚</span>
              <input
                type="text"
                name="topic"
                autocomplete="off"
                required
                placeholder="e.g. Diffusion models for generative art"
              />
            </div>
            <div class="field-hint">
              A detailed course (5 lessons) with real sources will be generated.
            </div>
          </div>
        </div>

        <div class="actions-row">
          <button class="submit-btn" type="submit">
            Generate course PDF
            <span class="chevron">↗</span>
          </button>
          <div class="meta">
            <span><strong>Depth:</strong> Standard (5-lesson course)</span>
            <span>Uses your key with Claude Sonnet + live web search.</span>
          </div>
        </div>
        {"<div class='status'>" + message + "</div>" if message else ""}
        {"<div class='status'>✅ Done — <a href='" + download_url + "'>download your course PDF</a></div>" if download_url else ""}
      </form>
    </div>
  </div>
</body>
</html>
"""
    return html


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return _render_page()

    api_key = (request.form.get("api_key") or "").strip()
    topic = (request.form.get("topic") or "").strip()

    if not api_key.startswith("sk-"):
        return _render_page("Error: API key should start with 'sk-'.")
    if not topic:
        return _render_page("Error: please enter a topic to research.")

    depth = _default_depth()

    try:
        client = nexus.anthropic.Anthropic(api_key=api_key)
    except Exception as exc:
        return _render_page(f"Error: could not initialize Anthropic client ({exc}).")

    try:
        data = nexus.do_research(client, topic, depth)
    except Exception as exc:
        return _render_page(f"Error: research failed ({exc}).")

    lessons = data.get("lessons", [])
    citations = data.get("citations", [])

    # Build PDF into a temporary folder but with a readable filename.
    safe_name = nexus.safe_filename(topic)
    tmp_dir = tempfile.mkdtemp(prefix="nexus_web_")
    output_path = os.path.join(tmp_dir, safe_name)

    try:
        nexus.build_pdf(topic, lessons, citations, output_path)
    except Exception as exc:
        return _render_page(f"Error: PDF generation failed ({exc}).")

    # Redirect to dedicated download route, so the browser triggers a file download.
    return redirect(url_for("download", path=output_path))


@app.route("/download")
def download():
    path = request.args.get("path", "")
    if not path or not os.path.exists(path):
        return _render_page("Error: file not found. Please run the research again.")
    filename = os.path.basename(path)
    # Stream the PDF to the user.
    return send_file(
        path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").strip() == "1"
    # Bind to 0.0.0.0 so platforms like Render can route traffic in.
    app.run(host="0.0.0.0", port=port, debug=debug)

