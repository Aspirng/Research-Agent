#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║            NEXUS RESEARCH AGENT  —  CLI Edition          ║
║      Powered by Anthropic Claude + Live Web Search       ║
╚══════════════════════════════════════════════════════════╝

Usage:
    python nexus_research.py

Requirements:
    pip install anthropic reportlab
"""

import os
import sys
import json
import re
import textwrap
from datetime import datetime
from getpass import getpass

import anthropic

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import (
    HexColor, white, black
)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus.flowables import Flowable

# ── Colour palette ────────────────────────────────────────────────────────────
PURPLE      = HexColor("#7c6dfa")
PURPLE_LITE = HexColor("#ede9fe")
PURPLE_MID  = HexColor("#c4b5fd")
DARK        = HexColor("#0d0d1a")
DARK2       = HexColor("#1a1a2e")
BODY_TEXT   = HexColor("#2c2c3e")
MUTED       = HexColor("#6b6b82")
ACCENT_ORG  = HexColor("#fb923c")
ACCENT_BLUE = HexColor("#38bdf8")
SUCCESS     = HexColor("#34d399")
BG_LIGHT    = HexColor("#f7f6ff")
BORDER_CLR  = HexColor("#e2e0f8")
WHITE       = white


# ── Custom Flowable: coloured rule ────────────────────────────────────────────
class ColorRule(Flowable):
    def __init__(self, width, color=PURPLE, thickness=1.5):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness
        self.height = thickness + 2

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.thickness / 2, self.width, self.thickness / 2)


# ── Custom Flowable: left-border accent box ───────────────────────────────────
class AccentBox(Flowable):
    def __init__(self, text, width, bg=BG_LIGHT, border=PURPLE, font_size=10):
        super().__init__()
        self.text = text
        self.width = width
        self.bg = bg
        self.border_col = border
        self.font_size = font_size
        self.pad = 10

    def wrap(self, availW, availH):
        # estimate height from line count
        chars_per_line = max(1, int((self.width - self.pad * 2 - 6) / (self.font_size * 0.55)))
        lines = max(1, len(self.text) // chars_per_line + self.text.count("\n") + 1)
        self.height = lines * (self.font_size * 1.5) + self.pad * 2
        return self.width, self.height

    def draw(self):
        c = self.canv
        h = self.height
        # background
        c.setFillColor(self.bg)
        c.roundRect(0, 0, self.width, h, 5, stroke=0, fill=1)
        # left border
        c.setFillColor(self.border_col)
        c.rect(0, 0, 4, h, stroke=0, fill=1)
        # text
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica-Oblique", self.font_size)
        tw = self.width - self.pad * 2 - 6
        wrapped = textwrap.wrap(self.text, width=max(10, int(tw / (self.font_size * 0.52))))
        y = h - self.pad - self.font_size
        for line in wrapped:
            if y < self.pad:
                break
            c.drawString(self.pad + 6, y, line)
            y -= self.font_size * 1.5


# ── Custom Flowable: keypoints box ───────────────────────────────────────────
class KeypointsBox(Flowable):
    def __init__(self, title, points, width):
        super().__init__()
        self.title = title
        self.points = points
        self.width = width
        self.fsize = 10
        self.pad = 12

    def wrap(self, availW, availH):
        cpl = max(1, int((self.width - self.pad * 2 - 16) / (self.fsize * 0.55)))
        total_lines = 2  # label + gap
        for p in self.points:
            total_lines += max(1, len(p) // cpl + 1) + 0.3
        self.height = total_lines * self.fsize * 1.55 + self.pad * 2
        return self.width, self.height

    def draw(self):
        c = self.canv
        h = self.height
        c.setFillColor(PURPLE_LITE)
        c.roundRect(0, 0, self.width, h, 6, stroke=0, fill=1)
        c.setStrokeColor(BORDER_CLR)
        c.setLineWidth(0.8)
        c.roundRect(0, 0, self.width, h, 6, stroke=1, fill=0)

        y = h - self.pad - self.fsize
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(PURPLE)
        c.drawString(self.pad, y, "KEY TAKEAWAYS")
        y -= self.fsize * 1.8

        tw = self.width - self.pad * 2 - 16
        for point in self.points:
            if y < self.pad:
                break
            wrapped = textwrap.wrap(point, width=max(10, int(tw / (self.fsize * 0.52))))
            c.setFont("Helvetica", self.fsize)
            c.setFillColor(BODY_TEXT)
            # bullet arrow
            c.setFillColor(PURPLE)
            c.drawString(self.pad, y, "›")
            c.setFillColor(BODY_TEXT)
            for k, line in enumerate(wrapped):
                if y < self.pad:
                    break
                c.drawString(self.pad + 12, y, line)
                y -= self.fsize * 1.5
            y -= self.fsize * 0.4


# ── PDF styles ────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    S = {}

    def add(name, **kw):
        S[name] = ParagraphStyle(name, parent=base["Normal"], **kw)

    add("cover_brand",
        fontName="Helvetica-Bold", fontSize=9, textColor=PURPLE,
        spaceAfter=30, letterSpacing=3)

    add("cover_title",
        fontName="Helvetica-Bold", fontSize=34, textColor=DARK,
        leading=40, spaceAfter=12, letterSpacing=-0.5)

    add("cover_sub",
        fontName="Helvetica", fontSize=12, textColor=MUTED,
        spaceAfter=6)

    add("cover_meta",
        fontName="Helvetica", fontSize=9, textColor=MUTED,
        spaceAfter=4)

    add("section_label",
        fontName="Helvetica-Bold", fontSize=8, textColor=PURPLE,
        spaceAfter=4, letterSpacing=2)

    add("section_title",
        fontName="Helvetica-Bold", fontSize=22, textColor=DARK,
        leading=26, spaceAfter=14)

    add("toc_num",
        fontName="Helvetica-Bold", fontSize=9, textColor=PURPLE)

    add("toc_name",
        fontName="Helvetica", fontSize=11, textColor=DARK2)

    add("toc_type",
        fontName="Helvetica", fontSize=8.5, textColor=MUTED)

    add("lesson_num_label",
        fontName="Helvetica-Bold", fontSize=8, textColor=PURPLE,
        spaceAfter=4, letterSpacing=2)

    add("lesson_title",
        fontName="Helvetica-Bold", fontSize=20, textColor=DARK,
        leading=26, spaceAfter=10)

    add("lesson_type",
        fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_ORG,
        spaceAfter=4, letterSpacing=1)

    add("sub_heading",
        fontName="Helvetica-Bold", fontSize=13, textColor=DARK2,
        spaceBefore=14, spaceAfter=8, leading=17)

    add("body_para",
        fontName="Helvetica", fontSize=11, textColor=BODY_TEXT,
        leading=18, spaceAfter=8, alignment=TA_JUSTIFY)

    add("source_item",
        fontName="Helvetica", fontSize=9, textColor=PURPLE,
        spaceAfter=4)

    add("cit_num",
        fontName="Helvetica-Bold", fontSize=9.5, textColor=PURPLE)

    add("cit_title",
        fontName="Helvetica-Bold", fontSize=11, textColor=DARK2,
        spaceAfter=2)

    add("cit_url",
        fontName="Helvetica", fontSize=9, textColor=ACCENT_BLUE,
        spaceAfter=8)

    add("footer",
        fontName="Helvetica", fontSize=7.5, textColor=MUTED,
        alignment=TA_CENTER)

    return S


# ── Page template with header/footer ─────────────────────────────────────────
def make_page_template(canvas, doc):
    canvas.saveState()
    W, H = A4
    # header line (skip cover page)
    if doc.page > 1:
        canvas.setStrokeColor(PURPLE)
        canvas.setLineWidth(0.4)
        canvas.line(20*mm, H - 12*mm, W - 20*mm, H - 12*mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20*mm, H - 10*mm, "NEXUS RESEARCH AGENT")
        canvas.drawRightString(W - 20*mm, H - 10*mm, f"Page {doc.page}")
        # footer
        canvas.setLineWidth(0.3)
        canvas.setStrokeColor(BORDER_CLR)
        canvas.line(20*mm, 12*mm, W - 20*mm, 12*mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(W/2, 9*mm, "Nexus Research Agent  ·  Anthropic Claude + Web Search")
    canvas.restoreState()


# ── Build PDF ─────────────────────────────────────────────────────────────────
def build_pdf(topic: str, lessons: list, citations: list, output_path: str):
    W, H = A4
    content_w = W - 40*mm  # 20mm each side

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=18*mm,
        title=f"Nexus Research: {topic}",
        author="Nexus Research Agent",
    )

    S = make_styles()
    story = []
    date_str = datetime.now().strftime("%B %d, %Y")

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("NEXUS RESEARCH AGENT", S["cover_brand"]))
    story.append(ColorRule(content_w, PURPLE, 0.8))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(topic.upper(), S["cover_title"]))
    story.append(Paragraph("Step-by-Step Educational Course  ·  AI-Generated with Web Sources", S["cover_sub"]))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"Generated: {date_str}", S["cover_meta"]))
    story.append(Paragraph(f"Lessons: {len(lessons)}  ·  Sources: {len(citations)}", S["cover_meta"]))
    story.append(Paragraph("Powered by Anthropic Claude + Live Web Search", S["cover_meta"]))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ─────────────────────────────────────────────────────
    story.append(Paragraph("CONTENTS", S["section_label"]))
    story.append(Paragraph("Table of Contents", S["section_title"]))
    story.append(ColorRule(content_w, PURPLE, 1.5))
    story.append(Spacer(1, 6*mm))

    toc_data = []
    for i, lesson in enumerate(lessons):
        num_str   = str(i + 1).zfill(2)
        title_str = lesson.get("title", f"Lesson {i+1}")
        type_str  = lesson.get("type", "Lesson")
        toc_data.append([
            Paragraph(num_str, S["toc_num"]),
            Paragraph(title_str, S["toc_name"]),
            Paragraph(type_str, S["toc_type"]),
        ])
    # Citations row
    toc_data.append([
        Paragraph("—", S["toc_num"]),
        Paragraph("References & Citations", S["toc_name"]),
        Paragraph("End", S["toc_type"]),
    ])

    col_widths = [12*mm, content_w - 40*mm, 28*mm]
    toc_table = Table(toc_data, colWidths=col_widths, hAlign="LEFT")
    toc_table.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW",   (0, 0), (-1, -2), 0.5, BORDER_CLR),
        ("LINEBELOW",   (0, -1),(-1, -1), 0.5, BORDER_CLR),
        ("TOPPADDING",  (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0,0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # ── LESSONS ───────────────────────────────────────────────────────────────
    for i, lesson in enumerate(lessons):
        lesson_num   = str(i + 1).zfill(2)
        lesson_title = lesson.get("title", f"Lesson {i+1}")
        lesson_type  = lesson.get("type", "Core Concept").upper()
        lesson_sum   = lesson.get("summary", "")
        subsections  = lesson.get("subsections", [])
        sources      = lesson.get("sources", [])

        header_items = [
            Paragraph(f"LESSON {lesson_num}  ·  {lesson_type}", S["lesson_num_label"]),
            Paragraph(lesson_title, S["lesson_title"]),
            ColorRule(content_w, PURPLE, 1.2),
            Spacer(1, 4*mm),
        ]
        if lesson_sum:
            header_items.append(AccentBox(lesson_sum, content_w))
            header_items.append(Spacer(1, 5*mm))

        story.extend(header_items)

        for sub in subsections:
            heading   = sub.get("heading", "")
            paragraphs = sub.get("paragraphs", [])
            keypoints = sub.get("keypoints", [])

            block = []
            block.append(Paragraph(heading, S["sub_heading"]))
            for para_text in paragraphs:
                block.append(Paragraph(para_text, S["body_para"]))
            if keypoints:
                block.append(Spacer(1, 3*mm))
                block.append(KeypointsBox("KEY TAKEAWAYS", keypoints, content_w))
                block.append(Spacer(1, 4*mm))
            story.extend(block)

        if sources:
            story.append(Spacer(1, 4*mm))
            story.append(ColorRule(content_w, BORDER_CLR, 0.5))
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("SOURCES", S["lesson_num_label"]))
            for src in sources:
                src_title = src.get("title", src.get("url", ""))
                src_url   = src.get("url", "")
                story.append(Paragraph(
                    f'↗ <a href="{src_url}" color="#7c6dfa">{src_title}</a>',
                    S["source_item"]
                ))

        if i < len(lessons) - 1:
            story.append(PageBreak())

    story.append(PageBreak())

    # ── CITATIONS PAGE ────────────────────────────────────────────────────────
    story.append(Paragraph("BIBLIOGRAPHY", S["section_label"]))
    story.append(Paragraph("References & Citations", S["section_title"]))
    story.append(ColorRule(content_w, PURPLE, 1.5))
    story.append(Spacer(1, 6*mm))

    for i, cit in enumerate(citations):
        cit_title = cit.get("title", f"Source {i+1}")
        cit_url   = cit.get("url", "")
        block = KeepTogether([
            Paragraph(f"[{i+1}]  {cit_title}", S["cit_title"]),
            Paragraph(
                f'<a href="{cit_url}" color="#38bdf8">{cit_url}</a>',
                S["cit_url"]
            ),
            HRFlowable(width="100%", thickness=0.4, color=BORDER_CLR, spaceAfter=6),
        ])
        story.append(block)

    doc.build(story, onFirstPage=make_page_template, onLaterPages=make_page_template)
    print(f"\n  ✅  PDF saved → {output_path}")


# ── Research engine ───────────────────────────────────────────────────────────
def do_research(client: anthropic.Anthropic, topic: str, depth: str) -> dict:
    depth_map = {
        "1": "3 lessons. Each lesson: 2 subsections, each with 3 paragraphs and 3 keypoints.",
        "2": "5 lessons. Each lesson: 3 subsections, each with 4 paragraphs and 4 keypoints.",
        "3": "7 lessons. Each lesson: 4 subsections, each with 5 paragraphs and 5 keypoints.",
    }

    SYSTEM = f"""You are an expert educator and researcher. Create a structured, step-by-step educational course on the given topic — like a university textbook.

Use the web_search tool multiple times to find real, current information and sources before writing.

After all research is complete, output ONLY a raw JSON object. No markdown code fences, no explanation text before or after. Your response must start with {{ and end with }}.

JSON schema:
{{
  "lessons": [
    {{
      "title": "string",
      "type": "Introduction | Fundamentals | Core Concept | Deep Dive | Application | Advanced | Summary",
      "summary": "string (2 sentences)",
      "subsections": [
        {{
          "heading": "string",
          "paragraphs": ["string", "string", "string"],
          "keypoints": ["string", "string", "string"]
        }}
      ],
      "sources": [
        {{ "title": "string", "url": "string" }}
      ]
    }}
  ],
  "citations": [
    {{ "title": "string", "url": "string" }}
  ]
}}

Requirements:
- {depth_map[depth]}
- Each paragraph: 3-5 complete educational sentences
- Teach progressively from basics to advanced across lessons
- Sources must be real, working URLs (Wikipedia, official docs, MDN, arXiv, etc.)
- Each lesson needs at least 2 real sources
- Return ONLY the JSON. Nothing else. Start with {{"""

    print("\n  🔍  Searching the web and gathering sources...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=12000,
        system=SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": f'Create a full educational course on: "{topic}"\n\nSearch the web for real information, then return ONLY the JSON object.'
        }]
    )

    raw_text = "".join(
        block.text for block in response.content
        if hasattr(block, "text") and block.text
    )

    print("  🧠  Parsing research data...")

    parsed = None

    # Strategy 1: direct parse
    try:
        parsed = json.loads(raw_text.strip())
    except Exception:
        pass

    # Strategy 2: strip markdown fences
    if not (parsed and parsed.get("lessons")):
        try:
            clean = re.sub(r"```json\s*", "", raw_text, flags=re.IGNORECASE)
            clean = re.sub(r"```\s*", "", clean).strip()
            parsed = json.loads(clean)
        except Exception:
            pass

    # Strategy 3: find outermost braces
    if not (parsed and parsed.get("lessons")):
        try:
            start = raw_text.index("{")
            end   = raw_text.rindex("}")
            parsed = json.loads(raw_text[start:end+1])
        except Exception:
            pass

    # Strategy 4: regex for JSON blob with "lessons"
    if not (parsed and parsed.get("lessons")):
        match = re.search(r'\{[\s\S]*?"lessons"[\s\S]*?\}(?=\s*$)', raw_text)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                pass

    # Strategy 5: ask Claude to repair JSON
    if not (parsed and parsed.get("lessons")):
        print("  🔧  Repairing JSON structure...")
        fix_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system='Return ONLY valid raw JSON. No markdown. No explanation. Start with {',
            messages=[{
                "role": "user",
                "content": f'Extract and return valid JSON with a "lessons" array from this:\n\n{raw_text[:10000]}'
            }]
        )
        fix_text = "".join(
            b.text for b in fix_response.content if hasattr(b, "text") and b.text
        )
        try:
            s = fix_text.index("{")
            e = fix_text.rindex("}")
            parsed = json.loads(fix_text[s:e+1])
        except Exception:
            pass

    if not (parsed and isinstance(parsed.get("lessons"), list) and parsed["lessons"]):
        raise ValueError("Could not parse research data. Please try again.")

    return parsed


# ── CLI helpers ───────────────────────────────────────────────────────────────
def banner():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║            NEXUS RESEARCH AGENT  —  CLI Edition          ║")
    print("║      Powered by Anthropic Claude + Live Web Search       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


def pick_depth() -> str:
    print("  Select research depth:")
    print("    [1]  ⚡  Quick      — 3 lessons")
    print("    [2]  ⚖   Standard  — 5 lessons  (recommended)")
    print("    [3]  🔬  Deep Dive  — 7 lessons")
    while True:
        choice = input("\n  Your choice [1/2/3]: ").strip()
        if choice in ("1", "2", "3"):
            return choice
        print("  Please enter 1, 2, or 3.")


def safe_filename(topic: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9\s_-]", "", topic)
    clean = re.sub(r"\s+", "_", clean.strip()).lower()[:50]
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"nexus_{clean}_{ts}.pdf"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    banner()

    # ── API Key ───────────────────────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("  Enter your Anthropic API key (or set ANTHROPIC_API_KEY env var):")
        print("  Get one free at https://console.anthropic.com\n")
        api_key = getpass("  API Key: ").strip()
    if not api_key.startswith("sk-"):
        print("\n  ❌  Invalid API key format. Should start with 'sk-'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # ── Topic ─────────────────────────────────────────────────────────────────
    print()
    topic = input("  📚  Research topic: ").strip()
    if not topic:
        print("  ❌  No topic entered.")
        sys.exit(1)

    # ── Depth ─────────────────────────────────────────────────────────────────
    print()
    depth = pick_depth()

    depth_labels = {"1": "Quick (3 lessons)", "2": "Standard (5 lessons)", "3": "Deep Dive (7 lessons)"}
    print(f"\n  ┌─────────────────────────────────────────┐")
    print(f"  │  Topic : {topic[:40]:<40} │")
    print(f"  │  Depth : {depth_labels[depth]:<40} │")
    print(f"  └─────────────────────────────────────────┘")

    # ── Research ──────────────────────────────────────────────────────────────
    try:
        data = do_research(client, topic, depth)
    except Exception as e:
        print(f"\n  ❌  Research failed: {e}")
        sys.exit(1)

    lessons   = data.get("lessons", [])
    raw_cits  = data.get("citations", [])

    # Deduplicate citations across all lesson sources + top-level citations
    seen_urls = set()
    citations = []
    for lesson in lessons:
        for src in lesson.get("sources", []):
            url = src.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                citations.append(src)
    for cit in raw_cits:
        url = cit.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            citations.append(cit)

    print(f"\n  📖  Generated {len(lessons)} lessons with {len(citations)} sources.")

    # ── Output path ───────────────────────────────────────────────────────────
    default_name = safe_filename(topic)
    print(f"\n  Output filename (press Enter for default):")
    user_name = input(f"  [{default_name}]: ").strip()
    output_path = user_name if user_name else default_name
    if not output_path.endswith(".pdf"):
        output_path += ".pdf"

    # ── Build PDF ─────────────────────────────────────────────────────────────
    print(f"\n  📄  Building PDF...")
    try:
        build_pdf(topic, lessons, citations, output_path)
    except Exception as e:
        print(f"\n  ❌  PDF generation failed: {e}")
        raise

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("  ════════════════════════════════════════")
    print(f"  ✅  Done!  →  {output_path}")
    print(f"  📚  {len(lessons)} lessons  ·  {len(citations)} sources")
    print("  ════════════════════════════════════════")
    print()

    # Print lesson titles as a quick overview
    print("  Course outline:")
    for i, lesson in enumerate(lessons):
        print(f"    {str(i+1).zfill(2)}. [{lesson.get('type','Lesson'):12}]  {lesson.get('title','')}")
    print()


if __name__ == "__main__":
    main()
