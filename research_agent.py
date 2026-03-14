#!/usr/bin/env python3
"""
Research Agent v2 — VS Code Edition
────────────────────────────────────
Researches any topic using Claude AI + web search,
then exports a professional cited PDF to your Desktop.

SETUP (one time in terminal):
    pip install anthropic reportlab

USAGE:
    1. Paste your API key into API_KEY below (or set ANTHROPIC_API_KEY env var)
    2. Press F5 in VS Code, or run: python research_agent.py
"""

import os, json, re, sys, subprocess
from datetime import datetime
import anthropic
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, PageBreak, Table, TableStyle
)
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # set via env or passed at runtime
MODEL   = "claude-sonnet-4-6"
OUTPUT  = os.path.expanduser("~/Desktop")           # where PDF is saved

# ── PDF COLOURS ───────────────────────────────────────────────────────────────
C_DARK   = colors.HexColor("#0D1117")
C_NAVY   = colors.HexColor("#1E3A5F")
C_ACCENT = colors.HexColor("#2563EB")
C_LIGHT  = colors.HexColor("#EFF6FF")
C_MUTED  = colors.HexColor("#64748B")
C_BORDER = colors.HexColor("#E2E8F0")
C_WHITE  = colors.white
C_ROW    = colors.HexColor("#FAFAFA")

CONF = {
    "high":   (colors.HexColor("#166534"), colors.HexColor("#DCFCE7"), "High Confidence"),
    "medium": (colors.HexColor("#92400E"), colors.HexColor("#FEF3C7"), "Medium Confidence"),
    "low":    (colors.HexColor("#991B1B"), colors.HexColor("#FEE2E2"), "Low Confidence"),
}

# ── HELPERS ───────────────────────────────────────────────────────────────────
def cite(text):
    text = text.replace("&", "&amp;").replace('"', "&quot;")
    text = re.sub(r'\[(\d+)\]',
        r'<super><font size="7" color="#2563EB"><b>[\1]</b></font></super>', text)
    return text

def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def make_styles():
    b = getSampleStyleSheet()
    return {
        "badge":  ParagraphStyle("badge",  parent=b["Normal"], fontSize=8.5,  textColor=colors.HexColor("#93C5FD"), fontName="Helvetica-Bold", leading=11, spaceAfter=6),
        "title":  ParagraphStyle("title",  parent=b["Normal"], fontSize=24,   textColor=C_WHITE,  fontName="Helvetica-Bold", leading=30, spaceAfter=8),
        "meta":   ParagraphStyle("meta",   parent=b["Normal"], fontSize=9,    textColor=colors.HexColor("#CBD5E1"), fontName="Helvetica", leading=14),
        "slbl":   ParagraphStyle("slbl",   parent=b["Normal"], fontSize=8.5,  textColor=C_ACCENT, fontName="Helvetica-Bold", leading=11, spaceAfter=6),
        "sbody":  ParagraphStyle("sbody",  parent=b["Normal"], fontSize=10.5, textColor=C_NAVY,   fontName="Helvetica", leading=17, alignment=TA_JUSTIFY),
        "stitle": ParagraphStyle("stitle", parent=b["Normal"], fontSize=14,   textColor=C_DARK,   fontName="Helvetica-Bold", leading=20, spaceBefore=20, spaceAfter=2),
        "body":   ParagraphStyle("body",   parent=b["Normal"], fontSize=10.5, textColor=colors.HexColor("#334155"), fontName="Helvetica", leading=17, spaceAfter=8, alignment=TA_JUSTIFY),
        "bullet": ParagraphStyle("bullet", parent=b["Normal"], fontSize=10.5, textColor=colors.HexColor("#334155"), fontName="Helvetica", leading=17, leftIndent=12, spaceAfter=4),
        "th":     ParagraphStyle("th",     parent=b["Normal"], fontSize=8.5,  textColor=C_MUTED,  fontName="Helvetica-Bold", leading=11),
        "td_n":   ParagraphStyle("td_n",   parent=b["Normal"], fontSize=9.5,  textColor=C_ACCENT, fontName="Helvetica-Bold", leading=13),
        "td_nm":  ParagraphStyle("td_nm",  parent=b["Normal"], fontSize=9.5,  textColor=C_DARK,   fontName="Helvetica-Bold", leading=13),
        "td_url": ParagraphStyle("td_url", parent=b["Normal"], fontSize=8.5,  textColor=C_ACCENT, fontName="Helvetica-Oblique", leading=12),
        "td_b":   ParagraphStyle("td_b",   parent=b["Normal"], fontSize=9,    textColor=colors.HexColor("#475569"), fontName="Helvetica", leading=12),
        "disc":   ParagraphStyle("disc",   parent=b["Normal"], fontSize=9.5,  textColor=colors.HexColor("#92400E"), fontName="Helvetica", leading=14, alignment=TA_JUSTIFY),
    }

# ── PDF BUILDER ───────────────────────────────────────────────────────────────
class ReportPDF:
    def __init__(self, topic, report, path):
        self.topic  = topic
        self.report = report
        self.path   = path
        self.st     = make_styles()
        self.story  = []
        self.W      = A4[0] - 5 * cm

    def _cover(self):
        date  = datetime.now().strftime("%B %d, %Y")
        n_src = len(self.report.get("sources", []))
        n_sec = len(self.report.get("sections", []))
        rows  = [
            [Paragraph("VERIFIED RESEARCH REPORT", self.st["badge"])],
            [Paragraph(esc(self.topic),             self.st["title"])],
            [Paragraph(f"Generated: {date}  ·  {n_sec} Sections  ·  {n_src} Sources  ·  Claude AI + Web Search", self.st["meta"])],
        ]
        tbl = Table(rows, colWidths=[self.W])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), C_DARK),
            ("LEFTPADDING",   (0,0),(-1,-1), 30), ("RIGHTPADDING",  (0,0),(-1,-1), 30),
            ("TOPPADDING",    (0,0),(0,0),   36),  ("TOPPADDING",    (1,0),(1,0),   6),
            ("TOPPADDING",    (2,0),(2,0),   6),   ("BOTTOMPADDING", (2,0),(2,0),   32),
        ]))
        self.story += [tbl, Spacer(1, .5*cm)]
        summ = self.report.get("executive_summary", "")
        if summ:
            box = Table([
                [Paragraph("EXECUTIVE SUMMARY", self.st["slbl"])],
                [Paragraph(cite(summ),           self.st["sbody"])],
            ], colWidths=[self.W])
            box.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), C_LIGHT),
                ("LINEAFTER",     (0,0),(0,-1),  3, C_ACCENT),
                ("LEFTPADDING",   (0,0),(-1,-1), 18), ("RIGHTPADDING",  (0,0),(-1,-1), 18),
                ("TOPPADDING",    (0,0),(0,0),   14), ("TOPPADDING",    (1,0),(1,0),   0),
                ("BOTTOMPADDING", (1,0),(1,0),   16),
            ]))
            self.story.append(box)
        self.story.append(PageBreak())

    def _section(self, sec):
        title   = sec.get("title", "")
        conf    = sec.get("confidence", "medium")
        content = sec.get("content", "")
        bullets = sec.get("bullets", [])
        fg, bg, label = CONF.get(conf, CONF["medium"])
        badge_s = ParagraphStyle("bs", parent=self.st["body"],
            fontSize=8.5, textColor=fg, fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT)
        row = Table([
            [Paragraph(esc(title), self.st["stitle"]), Paragraph(label, badge_s)]
        ], colWidths=[self.W * 0.68, self.W * 0.32])
        row.setStyle(TableStyle([
            ("VALIGN",        (0,0),(-1,-1), "BOTTOM"),
            ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 0),
            ("LEFTPADDING",   (0,0),(0,0),   0), ("RIGHTPADDING",  (0,0),(0,0),   8),
            ("LEFTPADDING",   (1,0),(1,0),   10),("RIGHTPADDING",  (1,0),(1,0),   10),
            ("TOPPADDING",    (1,0),(1,0),   4), ("BOTTOMPADDING", (1,0),(1,0),   4),
            ("BACKGROUND",    (1,0),(1,0),   bg),
        ]))
        self.story += [row, HRFlowable(width=36, thickness=2.5, color=C_ACCENT, spaceAfter=8, spaceBefore=4)]
        for p in content.split("\n\n"):
            p = p.strip()
            if p: self.story.append(Paragraph(cite(p), self.st["body"]))
        for b in bullets:
            b = b.strip().lstrip("•-* ")
            if b: self.story.append(Paragraph(f"• {cite(b)}", self.st["bullet"]))
        self.story.append(Spacer(1, .2*cm))

    def _sources(self):
        srcs = self.report.get("sources", [])
        if not srcs: return
        self.story += [
            PageBreak(),
            Paragraph("Verified Sources & References", self.st["stitle"]),
            HRFlowable(width=36, thickness=2.5, color=C_ACCENT, spaceAfter=10, spaceBefore=4),
        ]
        rows = [[Paragraph(h, self.st["th"]) for h in ["#", "Source", "URL", "Reliability", "Summary"]]]
        for i, src in enumerate(srcs, 1):
            name  = src.get("name","")     if isinstance(src, dict) else str(src)
            url   = src.get("url","—")     if isinstance(src, dict) else "—"
            rel   = src.get("reliability","medium") if isinstance(src, dict) else "medium"
            summ  = src.get("summary","—") if isinstance(src, dict) else "—"
            short = (url[:46]+"…") if len(url) > 48 else url
            rows.append([
                Paragraph(f"[{i}]",              self.st["td_n"]),
                Paragraph(f"<b>{esc(name)}</b>", self.st["td_nm"]),
                Paragraph(esc(short),            self.st["td_url"]),
                Paragraph(rel.capitalize(),      self.st["td_b"]),
                Paragraph(esc(summ),             self.st["td_b"]),
            ])
        tbl = Table(rows, colWidths=[.7*cm, 3.5*cm, 4.6*cm, 2.0*cm, 5.2*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0),  colors.HexColor("#F8FAFC")),
            ("LINEBELOW",     (0,0),(-1,0),  .8, C_BORDER),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [C_WHITE, C_ROW]),
            ("LINEBELOW",     (0,1),(-1,-1), .3, C_BORDER),
            ("TOPPADDING",    (0,0),(-1,-1), 7), ("BOTTOMPADDING", (0,0),(-1,-1), 7),
            ("LEFTPADDING",   (0,0),(-1,-1), 7), ("RIGHTPADDING",  (0,0),(-1,-1), 7),
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ]))
        self.story += [tbl, Spacer(1, .5*cm)]
        disc = ("Verification Notice: All claims include [n] source references. "
                "High-confidence claims appear in 2+ independent sources. "
                "Always verify critical decisions against primary sources.")
        box = Table([[Paragraph(disc, self.st["disc"])]], colWidths=[self.W])
        box.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#FFF7ED")),
            ("LINEALL",       (0,0),(-1,-1), .8, colors.HexColor("#FED7AA")),
            ("TOPPADDING",    (0,0),(-1,-1), 12), ("BOTTOMPADDING", (0,0),(-1,-1), 12),
            ("LEFTPADDING",   (0,0),(-1,-1), 14), ("RIGHTPADDING",  (0,0),(-1,-1), 14),
        ]))
        self.story.append(box)

    def build(self):
        doc = SimpleDocTemplate(self.path, pagesize=A4,
            leftMargin=2.5*cm, rightMargin=2.5*cm,
            topMargin=1.8*cm, bottomMargin=2.5*cm)
        self._cover()
        for sec in self.report.get("sections", []): self._section(sec)
        self._sources()
        doc.build(self.story)

# ── RESEARCH ──────────────────────────────────────────────────────────────────
def research(topic):
    if not API_KEY:
        raise ValueError(
            "\n  No API key found!\n"
            "  Option 1: Set environment variable — export ANTHROPIC_API_KEY='sk-ant-...'\n"
            "  Option 2: Paste your key into the API_KEY variable at the top of this file."
        )
    client = anthropic.Anthropic(api_key=API_KEY)
    system = """You are a rigorous research analyst. Return ONLY valid JSON — no markdown, no backticks, no preamble.

{
  "executive_summary": "2-3 sentence overview with [1] citations",
  "sections": [
    {
      "title": "Section Title",
      "confidence": "high|medium|low",
      "content": "Paragraphs with [n] after every fact. Double newline between paragraphs.",
      "bullets": ["Key point [1]", "Another point [2]"]
    }
  ],
  "sources": [
    {
      "name": "Publication name",
      "url": "https://real-url.com",
      "reliability": "high|medium|low",
      "summary": "One sentence description"
    }
  ]
}

Rules: Every factual sentence ends with [n]. 4-6 sections. 5-8 real URLs from search only. Never fabricate URLs."""

    print(f"\n  🔍  Researching: {topic}")
    print("  🌐  Running web searches (20-40 seconds)...\n")
    resp = client.messages.create(
        model=MODEL, max_tokens=5000, system=system,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": f"Research thoroughly with multiple web searches, return only JSON: {topic}"}],
    )
    searches = sum(1 for b in resp.content if b.type == "tool_use" and b.name == "web_search")
    print(f"  ✓  {searches} web search(es) performed")
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()
    s, e = raw.find("{"), raw.rfind("}")
    if s != -1 and e != -1: raw = raw[s:e+1]
    try:
        return json.loads(raw)
    except:
        return {"executive_summary": f"Research on: {topic}",
                "sections": [{"title": "Findings", "confidence": "medium", "content": raw, "bullets": []}],
                "sources": []}

# ── MAIN ──────────────────────────────────────────────────────────────────────
# ↓↓ EDIT THIS to set your topic, then press F5 ↓↓
TOPIC = "US Iran war 2026"
# ↑↑ ─────────────────────────────────────────── ↑↑

def main():
    print("\n" + "═"*50)
    print("  Research Agent v2  —  Verified & Cited")
    print("═"*50)
    topic = (sys.argv[1] if len(sys.argv) > 1 else TOPIC).strip()
    if not topic:
        print("  No topic set. Edit the TOPIC variable above this function."); return
    report = research(topic)
    n_src = len(report.get("sources", []))
    n_sec = len(report.get("sections", []))
    print(f"\n  📊  {n_sec} sections · {n_src} sources")
    preview = re.sub(r'\[\d+\]', '', report.get("executive_summary", "")).strip()[:140]
    print(f"  📝  {preview}...")
    print("\n  SECTIONS:")
    for i, sec in enumerate(report.get("sections", []), 1):
        conf = sec.get("confidence", "medium").upper()
        print(f"    {i}. {sec.get('title','Untitled')}  [{conf}]")
    safe = re.sub(r"[^\w\s-]", "", topic).strip().replace(" ", "_")[:50]
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT, f"research_{safe}_{ts}.pdf")
    print(f"\n  📄  Building PDF...")
    ReportPDF(topic, report, path).build()
    print(f"\n  ✅  Saved to Desktop → {os.path.basename(path)}")
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])

if __name__ == "__main__":
    main()
