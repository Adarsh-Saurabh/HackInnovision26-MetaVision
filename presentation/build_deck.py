"""Build the MetaVision pitch deck (16:9) and its speaker notes.

uv run --no-project --with python-pptx --with pillow python presentation/build_deck.py
"""

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"

# ------------------------------------------------------------------ palette
BG = RGBColor(0x0B, 0x12, 0x20)
PANEL = RGBColor(0x13, 0x1E, 0x31)
PANEL2 = RGBColor(0x1A, 0x27, 0x3D)
STROKE = RGBColor(0x2A, 0x3A, 0x57)
TEXT = RGBColor(0xF4, 0xF7, 0xFB)
MUTED = RGBColor(0x9A, 0xA9, 0xC0)
DIM = RGBColor(0x6C, 0x7C, 0x96)
INDIGO = RGBColor(0x8B, 0x9C, 0xFF)
TEAL = RGBColor(0x2D, 0xD4, 0xBF)
AMBER = RGBColor(0xFB, 0xBF, 0x24)
ROSE = RGBColor(0xFB, 0x71, 0x85)
GREEN = RGBColor(0x4A, 0xDE, 0x80)

BODY = "Segoe UI"
MONO = "Consolas"

W, H = 13.333, 7.5
M = 0.72  # page margin

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)


# ------------------------------------------------------------------ helpers
def slide_new():
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    return s


def rect(s, x, y, w, h, fill, line=None, radius=0.05, line_w=0.9, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        r.adjustments[0] = radius
    if fill is None:
        r.fill.background()
    else:
        r.fill.solid()
        r.fill.fore_color.rgb = fill
    if line is None:
        r.line.fill.background()
    else:
        r.line.color.rgb = line
        r.line.width = Pt(line_w)
    r.shadow.inherit = False
    return r


def text(s, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, margins=(0, 0, 0, 0)):
    """paras: list of dicts {runs:[(txt, {size,bold,color,font,italic})], size, color, bold,
    align, space_after, line}"""
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left, tf.margin_right, tf.margin_top, tf.margin_bottom = (Inches(v) for v in margins)
    first = True
    for para in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = para.get("align", PP_ALIGN.LEFT)
        p.line_spacing = para.get("line", 1.08)
        p.space_after = Pt(para.get("space_after", 0))
        p.space_before = Pt(para.get("space_before", 0))
        runs = para.get("runs") or [(para.get("text", ""), {})]
        for txt, opt in runs:
            r = p.add_run()
            r.text = txt
            f = r.font
            f.name = opt.get("font", para.get("font", BODY))
            f.size = Pt(opt.get("size", para.get("size", 14)))
            f.bold = opt.get("bold", para.get("bold", False))
            f.italic = opt.get("italic", False)
            f.color.rgb = opt.get("color", para.get("color", TEXT))
    return box


def kicker(s, label, num=None, color=INDIGO):
    rect(s, M, 0.46, 0.11, 0.11, color, radius=0.5, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, M + 0.22, 0.37, 8.5, 0.3,
         [{"runs": [(label, {"size": 9.5, "bold": True, "color": color})]}])
    if num:
        text(s, W - M - 1.2, 0.37, 1.2, 0.3,
             [{"runs": [(f"{num:02d}", {"size": 9.5, "color": DIM})], "align": PP_ALIGN.RIGHT}])


def title(s, lines, y=0.72, size=33, width=None):
    if isinstance(lines, str):
        lines = [lines]
    paras = []
    for line in lines:
        if isinstance(line, tuple):
            txt, col = line
            paras.append({"runs": [(txt, {"size": size, "bold": True, "color": col})], "line": 1.02})
        else:
            paras.append({"runs": [(line, {"size": size, "bold": True, "color": TEXT})], "line": 1.02})
    text(s, M, y, width or (W - 2 * M), 0.62 * len(lines) + 0.15, paras)


def footer(s, num, total=13):
    rect(s, M, 7.02, W - 2 * M, 0.008, STROKE, shape=MSO_SHAPE.RECTANGLE)
    text(s, M, 7.1, 6, 0.25,
         [{"runs": [("MetaVision · Second Brain", {"size": 8.5, "color": DIM})]}])
    text(s, W - M - 4.5, 7.1, 4.5, 0.25,
         [{"runs": [(f"HackInnovision 2026 · Track B        {num:02d} / {total:02d}",
                     {"size": 8.5, "color": DIM})], "align": PP_ALIGN.RIGHT}])


def label(s, x, y, w, txt, color=MUTED, size=9):
    text(s, x, y, w, 0.25, [{"runs": [(txt, {"size": size, "bold": True, "color": color})]}])


def stat(s, x, y, w, value, caption, color=TEXT):
    text(s, x, y, w, 0.7, [{"runs": [(value, {"size": 33, "bold": True, "color": color})]}])
    text(s, x, y + 0.62, w, 0.55,
         [{"runs": [(caption, {"size": 10.5, "color": MUTED})], "line": 1.12}])


def bullets(s, x, y, w, items, size=12.5, color=MUTED, gap=0.42, dot=INDIGO):
    for i, item in enumerate(items):
        yy = y + i * gap
        rect(s, x, yy + 0.1, 0.08, 0.08, dot, radius=0.5, shape=MSO_SHAPE.OVAL)
        text(s, x + 0.2, yy, w - 0.2, gap,
             [{"runs": [(item, {"size": size, "color": color})], "line": 1.15}])


def notes(s, body):
    s.notes_slide.notes_text_frame.text = body


TOTAL = 13


# ================================================================== 1. cover
s = slide_new()
# faint geometry
rect(s, 9.4, -1.4, 5.2, 5.2, PANEL, radius=0.5, shape=MSO_SHAPE.OVAL)
rect(s, 11.2, 3.6, 3.4, 3.4, PANEL, radius=0.5, shape=MSO_SHAPE.OVAL)

kicker(s, "HACKINNOVISION 2026  ·  TRACK B  ·  AGENTIC WORKFLOW AUTOMATION", 1, color=TEAL)
rect(s, M, 1.62, 1.15, 0.045, TEAL, shape=MSO_SHAPE.RECTANGLE)
text(s, M, 1.9, 10.6, 2.9, [
    {"runs": [("One email.", {"size": 58, "bold": True, "color": TEXT})], "line": 1.0},
    {"runs": [("Many broken promises.", {"size": 58, "bold": True, "color": INDIGO})], "line": 1.0},
])
text(s, M, 4.15, 8.4, 1.2, [
    {"runs": [("MetaVision is the second brain that traces one change across every tool, "
               "proposes a safe plan, and proves it happened.", {"size": 16, "color": MUTED})], "line": 1.3},
])
for i, (v, c) in enumerate([("18", "records affected by one email"),
                            ("3", "independent approval scopes"),
                            ("0", "duplicate effects on replay")]):
    x = M + i * 3.15
    text(s, x, 5.62, 1.2, 0.5, [{"runs": [(v, {"size": 24, "bold": True, "color": TEAL})]}])
    text(s, x + 0.72, 5.7, 2.3, 0.6, [{"runs": [(c, {"size": 9.5, "color": MUTED})], "line": 1.1}])

rect(s, M, 6.62, W - 2 * M, 0.012, STROKE, shape=MSO_SHAPE.RECTANGLE)
text(s, M, 6.78, 6, 0.3, [{"runs": [("Built by Ujjwal · Adarsh · Vaibhav", {"size": 10, "color": DIM})]}])
text(s, W - M - 4, 6.78, 4, 0.3, [{"runs": [("14 November 2026  ·  IST", {"size": 10, "color": DIM})],
                                    "align": PP_ALIGN.RIGHT}])
notes(s, """TIMING 0:00–0:40
Open on the headline, not the tech. Say: "At 6:10 this morning, a sponsor cuts their sponsorship by forty thousand rupees. Somewhere in this team's tools, a banner is already printing and a post is already scheduled. Nothing in their software connects those facts."

Then the one-liner: "MetaVision is a second brain that notices the change, finds everything it affects, and helps a human act safely."

Do not read the three statistics yet. They land later. Do not introduce the team by name unless the judges expect it.""")

# ================================================================== 2. problem
s = slide_new()
kicker(s, "THE PROBLEM", 2)
title(s, [("The work lives in five apps.", TEXT), ("The promise lives in none of them.", MUTED)])

# quote card
rect(s, M, 1.95, 4.7, 3.35, PANEL, STROKE)
rect(s, M, 1.95, 0.05, 3.35, INDIGO, shape=MSO_SHAPE.RECTANGLE)
label(s, M + 0.3, 2.12, 4.1, "GMAIL  ·  06:10 IST  ·  VERIFIED CONTACT")
text(s, M + 0.3, 2.45, 4.1, 1.9, [
    {"runs": [("“Please revise Aster Labs’ commitment from ₹1,00,000 to ₹60,000. "
               "Send an updated benefits proposal by 18:00 IST tomorrow.”",
               {"size": 15, "color": TEXT, "italic": True})], "line": 1.35},
])
text(s, M + 0.3, 4.62, 4.1, 0.5,
     [{"runs": [("Priya Nair · Aster Labs", {"size": 10, "color": MUTED})]}])

rows = [
    ("Sponsor tracker", "Aster is still Gold · ₹1,00,000", AMBER),
    ("Budget sheet", "Forecast still says +₹30,000", AMBER),
    ("Team chat", "PH-2231 is already in production", ROSE),
    ("Calendar", "DEC-07 review still assumes a surplus", AMBER),
    ("Docs & social", "Four benefits promised at Gold level", ROSE),
]
label(s, 5.95, 1.92, 6.6, "WHAT IS NOW WRONG — AND NOBODY HAS NOTICED")
for i, (app, stale, color) in enumerate(rows):
    y = 2.24 + i * 0.62
    rect(s, 5.95, y, 6.66, 0.52, PANEL, STROKE, radius=0.12)
    rect(s, 6.08, y + 0.19, 0.13, 0.13, color, radius=0.5, shape=MSO_SHAPE.OVAL)
    text(s, 6.33, y + 0.06, 1.85, 0.4,
         [{"runs": [(app, {"size": 11.5, "bold": True, "color": TEXT})]}])
    text(s, 8.15, y + 0.07, 4.3, 0.4,
         [{"runs": [(stale, {"size": 10.5, "color": MUTED})]}])

rect(s, M, 5.62, W - 2 * M, 1.05, PANEL2, None, radius=0.1)
rect(s, M, 5.62, 0.05, 1.05, TEAL, shape=MSO_SHAPE.RECTANGLE)
text(s, M + 0.3, 5.76, 11.4, 0.8, [
    {"runs": [("The cost is not the email. It is the dependency the email breaks — discovered days later, "
               "after the banner is printed and the post is live.", {"size": 14, "color": TEXT})], "line": 1.25},
])
footer(s, 2, TOTAL)
notes(s, """TIMING 0:40–1:20
Point at the email, then at the five rows. "This is the actual failure mode: not missing data, but stale relationships between data." Give one concrete example: the print order PH-2231 is mentioned only in chat. The tracker never knew it existed.

Close the slide on the bottom line: "The risk is the dependency, not the message." Then move on — do not list every record.""")

# ================================================================== 3. idea
s = slide_new()
kicker(s, "THE IDEA", 3)
title(s, "A second brain for dependencies.")
text(s, M, 1.62, 11.4, 0.4,
     [{"runs": [("Six small agents, one human gate, and a verifier that trusts nothing it did not read back.",
                 {"size": 13, "color": MUTED})]}])

steps = [
    ("01", "Detect", "Who changed what — with the exact source span.", INDIGO),
    ("02", "Trace", "Walk the graph to every record the change touches.", INDIGO),
    ("03", "Plan", "Exact diffs, plus what must not be automated.", INDIGO),
    ("04", "Approve", "Three permissions. Nothing writes before yes.", AMBER),
    ("05", "Execute", "Version checks, bounded retries, adaptive replan.", INDIGO),
    ("06", "Verify", "Read every record back. Recompute the money.", TEAL),
]
cw = 1.86
for i, (num, name, desc, color) in enumerate(steps):
    x = M + i * (cw + 0.16)
    rect(s, x, 2.18, cw, 2.2, PANEL, STROKE)
    rect(s, x, 2.18, cw, 0.05, color, radius=0, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.18, 2.33, 0.8, 0.3, [{"runs": [(num, {"size": 10, "bold": True, "color": color})]}])
    text(s, x + 0.18, 2.64, cw - 0.3, 0.4, [{"runs": [(name, {"size": 15, "bold": True, "color": TEXT})]}])
    text(s, x + 0.18, 3.1, cw - 0.32, 1.1, [{"runs": [(desc, {"size": 10, "color": MUTED})], "line": 1.22}])

# two lanes
rect(s, M, 4.78, 5.86, 1.62, PANEL, STROKE)
label(s, M + 0.26, 4.94, 5.3, "WHAT THE MODEL DOES", INDIGO)
text(s, M + 0.26, 5.22, 5.35, 1.05, [
    {"runs": [("Reads free text. Extracts claims with evidence. Infers links. Drafts wording.",
               {"size": 12.5, "color": TEXT})], "line": 1.25},
])
rect(s, 6.82, 4.78, 5.79, 1.62, PANEL, STROKE)
label(s, 7.08, 4.94, 5.3, "WHAT IT NEVER DOES", ROSE)
text(s, 7.08, 5.22, 5.3, 1.05, [
    {"runs": [("Decide money. Skip approval. Overwrite a newer record. Claim success without read-back.",
               {"size": 12.5, "color": TEXT})], "line": 1.25},
])
footer(s, 3, TOTAL)
notes(s, """TIMING 1:20–2:00
Walk the six steps quickly, one sentence each. The key sentence is the split at the bottom: "The model is allowed to read language and suggest links. It is not allowed to move money, skip the gate, or declare success."

If asked why six agents: separate permissions and an independent verifier. Keep this answer short here; slide 9 has the architecture.""")

# ================================================================== 4. scenario
s = slide_new()
kicker(s, "THE DEMO SCENARIO", 4)
title(s, [("₹40,000 less.", TEXT), ("A Gold sponsor becomes Silver.", MUTED)])

label(s, M, 1.9, 5.2, "BEFORE  →  AFTER")
fin = [
    ("Commitments", "₹2,50,000", "₹2,10,000", TEXT),
    ("Planned expenses", "₹2,20,000", "₹2,20,000", TEXT),
    ("Forecast balance", "+₹30,000", "−₹10,000", ROSE),
    ("Sponsor tier", "Gold", "Silver", AMBER),
]
for i, (name, before, after, color) in enumerate(fin):
    y = 2.22 + i * 0.78
    rect(s, M, y, 5.35, 0.66, PANEL, STROKE, radius=0.1)
    text(s, M + 0.2, y + 0.2, 1.9, 0.3, [{"runs": [(name, {"size": 10.5, "color": MUTED})]}])
    text(s, M + 2.05, y + 0.14, 1.25, 0.4, [{"runs": [(before, {"size": 12.5, "bold": True, "color": TEXT})]}])
    text(s, M + 3.22, y + 0.17, 0.3, 0.3, [{"runs": [("→", {"size": 11, "color": DIM})]}])
    text(s, M + 3.55, y + 0.14, 1.7, 0.4, [{"runs": [(after, {"size": 12.5, "bold": True, "color": color})]}])

label(s, 6.5, 1.9, 6.2, "FOUR DELIVERABLES  ·  FOUR DIFFERENT ANSWERS")
deliv = [
    ("D1", "Main-stage banner", "in production", "HUMAN DECISION", AMBER),
    ("D2", "Social post #1", "published", "ALREADY SATISFIED", TEAL),
    ("D3", "Social post #2", "scheduled 16 Nov", "CANCEL", ROSE),
    ("D4", "Stage mention", "planned", "CANCEL", ROSE),
]
for i, (d, name, state, action, color) in enumerate(deliv):
    y = 2.22 + i * 0.78
    rect(s, 6.5, y, 6.11, 0.66, PANEL, STROKE, radius=0.1)
    text(s, 6.68, y + 0.17, 0.6, 0.3, [{"runs": [(d, {"size": 11, "bold": True, "color": INDIGO})]}])
    text(s, 7.18, y + 0.11, 2.1, 0.3, [{"runs": [(name, {"size": 11, "bold": True, "color": TEXT})]}])
    text(s, 7.18, y + 0.35, 2.1, 0.3, [{"runs": [(state, {"size": 9, "color": MUTED})]}])
    pw = 1.62
    rect(s, 10.87, y + 0.16, pw, 0.34, PANEL2, color, radius=0.3, line_w=0.8)
    text(s, 10.87, y + 0.22, pw, 0.25,
         [{"runs": [(action, {"size": 8.3, "bold": True, "color": color})], "align": PP_ALIGN.CENTER}])

rect(s, M, 5.72, W - 2 * M, 1.02, PANEL2, None, radius=0.1)
rect(s, M, 5.72, 0.05, 1.02, AMBER, shape=MSO_SHAPE.RECTANGLE)
text(s, M + 0.3, 5.85, 11.3, 0.8, [
    {"runs": [("Second-order effect:  ", {"size": 12.5, "bold": True, "color": AMBER}),
              ("DEC-07, the optional ₹25,000 DJ upgrade, is only approved if the balance is at least ₹25,000. "
               "It is now at risk — not rejected. That is a human decision.", {"size": 12.5, "color": TEXT})],
     "line": 1.22},
])
footer(s, 4, TOTAL)
notes(s, """TIMING 2:00–2:50
Set the scene fast. Before: three sponsors, ₹2.5 lakh committed against ₹2.2 lakh of costs, so a ₹30,000 cushion. After the cut: ₹2.1 lakh against the same costs, so a ₹10,000 hole.

Then the deliverable table. Emphasise that one rule change produces four different outcomes. D2 is not a mistake — the published post already satisfies Silver's one post. D1 is irreversible, so the system refuses to decide.

Mention DEC-07 at the bottom but do not over-explain it; it is the second-order effect judges remember.""")

# ================================================================== 5. impact map
s = slide_new()
kicker(s, "CONTEXT ENGINEERING", 5)
title(s, "It isn’t the sponsor. It’s everything downstream.")

img = ASSETS / "impact-graph.png"
if not img.exists():
    src = Image.open(ASSETS / "impact-map.png")
    src.crop((18, 76, 1962, 442)).save(img)
pic = s.shapes.add_picture(str(img), Inches(0.55), Inches(1.7), width=Inches(12.23))
text(s, 0.55, 1.7 + 12.23 * 366 / 1944 + 0.06, 12.2, 0.25,
     [{"runs": [("Actual rendered impact graph · indigo = affected · amber = human decision · rose = cancel or shortage · dashed = inferred",
                 {"size": 8.5, "color": DIM})]}])

cards = [
    ("INFERRED, NOT ASSUMED", "chat-014 says “order PH-2231”. PH-2231 is D1’s print order, so the link is inferred and marked as such.", INDIGO),
    ("SECOND-ORDER RISK", "DEC-07 is found by walking backwards over “contingent on budget” — a dependency no keyword search would catch.", AMBER),
    ("SPONSOR-SCOPED", "The tier policy is shared, but the walk only follows it for Aster. Brightline and Corvex stay untouched.", TEAL),
]
for i, (head, body, color) in enumerate(cards):
    x = M + i * 4.03
    rect(s, x, 4.72, 3.87, 1.62, PANEL, STROKE)
    rect(s, x, 4.72, 0.05, 1.62, color, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.24, 4.86, 3.45, 0.28, [{"runs": [(head, {"size": 9, "bold": True, "color": color})]}])
    text(s, x + 0.24, 5.16, 3.45, 1.1, [{"runs": [(body, {"size": 10.5, "color": TEXT})], "line": 1.2}])

text(s, M, 6.52, 11.8, 0.35,
     [{"runs": [("One email  →  18 affected records across 22 nodes, found by graph traversal — not by searching for keywords.",
                 {"size": 12, "color": MUTED})]}])
footer(s, 5, TOTAL)
notes(s, """TIMING 2:50–3:40
Let the graph breathe for two seconds. Point to the left (the two source messages), then follow the lines to the budget, decisions, deliverables and documents.

Name the three ideas on the cards, in this order: (1) inferred links are labelled, not silently trusted; (2) the second-order DEC-07 risk comes from walking backwards; (3) sponsor scoping is why Brightline and Corvex do not get dragged in.

This is the slide that answers "is it really a knowledge graph?" — typed nodes, provenance, traversal.""")

# ================================================================== 6. approval
s = slide_new()
kicker(s, "HUMAN IN CONTROL", 6)
title(s, "The plan is precise. The judgement stays human.")

# plan card
rect(s, M, 1.85, 7.25, 4.55, PANEL, STROKE)
text(s, M + 0.3, 2.0, 3.2, 0.3, [{"runs": [("PLAN V1", {"size": 9, "bold": True, "color": INDIGO})]}])
text(s, M + 0.3, 2.26, 6.6, 0.35,
     [{"runs": [("15 actions  ·  4 flags  ·  nothing applied yet", {"size": 13, "bold": True, "color": TEXT})]}])
row_data = [
    ("A1", "Sponsor · Aster Labs", "₹1,00,000 → ₹60,000   ·   Gold → Silver"),
    ("A5", "Deliverable · D4", "planned → cancelled"),
    ("A6", "Document · run sheet", "remove the stage mention"),
    ("A7", "Document · benefits", "Gold → Silver entitlements"),
    ("A8", "Calendar · sponsor review", "15 Nov, 12:00–12:30"),
    ("A13", "Email · sponsor reply", "save as draft — do not send"),
]
for i, (aid, what, change) in enumerate(row_data):
    y = 2.72 + i * 0.56
    rect(s, M + 0.28, y, 6.68, 0.46, PANEL2, None, radius=0.1)
    text(s, M + 0.42, y + 0.11, 0.45, 0.3, [{"runs": [(aid, {"size": 8.5, "bold": True, "color": DIM})]}])
    text(s, M + 0.86, y + 0.05, 2.3, 0.3, [{"runs": [(what, {"size": 9.5, "bold": True, "color": TEXT})]}])
    text(s, M + 0.86, y + 0.23, 5.9, 0.25, [{"runs": [(change, {"size": 9, "color": MUTED})]}])

# scopes
label(s, 8.35, 1.88, 4.2, "WHAT MAY RUN?")
scopes = [
    ("✓", "Business records", True, TEXT),
    ("✓", "Internal notifications", True, TEXT),
    ("", "Send to sponsor", False, MUTED),
]
for i, (mark, name, on, color) in enumerate(scopes):
    y = 2.2 + i * 0.52
    rect(s, 8.35, y, 0.24, 0.24, TEAL if on else PANEL2, None if on else STROKE, radius=0.2, line_w=0.8)
    if mark:
        text(s, 8.35, y + 0.015, 0.24, 0.22,
             [{"runs": [("✓", {"size": 10, "bold": True, "color": BG})], "align": PP_ALIGN.CENTER}])
    text(s, 8.72, y - 0.02, 3.3, 0.3, [{"runs": [(name, {"size": 11, "color": color})]}])
text(s, 8.35, 3.74, 4.2, 0.3,
     [{"runs": [("Reply stays a draft until sponsor send is approved.", {"size": 8.5, "color": DIM})]}])

rect(s, 8.35, 4.12, 4.28, 2.28, PANEL2, None, radius=0.1)
rect(s, 8.35, 4.12, 0.05, 2.28, AMBER, shape=MSO_SHAPE.RECTANGLE)
text(s, 8.58, 4.24, 3.9, 0.3,
     [{"runs": [("WHAT WE REFUSE TO DECIDE", {"size": 9, "bold": True, "color": AMBER})]}])
bullets(s, 8.58, 4.56, 3.9, [
    "D1 banner is already printing",
    "₹10,000 deficit — no invented cuts",
    "DEC-07 at risk, not rejected",
    "Silver wall logo still uncovered",
], size=9.5, gap=0.42, dot=AMBER)

text(s, M, 6.62, 11.9, 0.3, [
    {"runs": [("15 exact diffs.  ", {"size": 12, "bold": True, "color": TEXT}),
              ("3 independent permissions.  ", {"size": 12, "bold": True, "color": TEXT}),
              ("No business write before approval.", {"size": 12, "bold": True, "color": TEAL})]}])
footer(s, 6, TOTAL)
notes(s, """TIMING 3:00–3:30 (part of the demo lead-in)
Show three rows, not fifteen: the money, the irreversible deliverable, the draft that is not sent. Then the three permission boxes.

The line to say: "Approval is not a rubber stamp. The organiser sees exact before/after values and can allow business records without allowing an email to the sponsor."

The amber panel is the honest part: the system surfaces D1, the deficit, DEC-07 and the missing wall logo, and refuses to invent fixes.""")

# ================================================================== 7. demo
s = slide_new()
kicker(s, "LIVE DEMO  ·  3 MINUTES", 7, color=AMBER)
title(s, [("Watch the world change", TEXT), ("mid-plan.", AMBER)])

beats = [
    ("01", "Approve", "15 actions. Sponsor send stays off, so the reply is saved as a draft.", TEAL),
    ("02", "Retry", "Tracker fails before writing. Same operation key; second attempt lands.", INDIGO),
    ("03", "Conflict", "A teammate publishes D3 first (v1 → v2). We stop — never overwrite.", ROSE),
    ("04", "Replan", "Plan v2: 6 changed actions need approval; 4 done are reused, 3 stay covered.", AMBER),
]
for i, (num, name, body, color) in enumerate(beats):
    x = M + i * 3.08
    rect(s, x, 1.95, 2.9, 2.55, PANEL, STROKE)
    rect(s, x, 1.95, 2.9, 0.05, color, radius=0, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.24, 2.12, 0.7, 0.3, [{"runs": [(num, {"size": 10, "bold": True, "color": color})]}])
    text(s, x + 0.24, 2.44, 2.4, 0.4, [{"runs": [(name, {"size": 17, "bold": True, "color": TEXT})]}])
    text(s, x + 0.24, 2.98, 2.45, 1.35, [{"runs": [(body, {"size": 10.5, "color": MUTED})], "line": 1.24}])

rect(s, M, 4.78, W - 2 * M, 0.92, PANEL2, None, radius=0.1)
text(s, M + 0.3, 4.96, 11.2, 0.6, [
    {"runs": [("After the demo:  ", {"size": 12.5, "bold": True, "color": TEAL}),
              ("read back every changed record, then replay the same email 10× and prove nothing happens twice.",
               {"size": 12.5, "color": TEXT})], "line": 1.2},
])

text(s, M, 5.98, 5.9, 0.65, [
    {"runs": [("The failures are injected on purpose.", {"size": 11, "bold": True, "color": TEXT})], "line": 1.2},
    {"runs": [("Every number on screen comes from the real engine, not a canned animation.", {"size": 10.5, "color": MUTED})], "line": 1.2},
])
text(s, 7.1, 5.98, 5.5, 0.65, [
    {"runs": [("If the demo breaks:", {"size": 11, "bold": True, "color": TEXT})], "line": 1.2},
    {"runs": [("switch to the recorded run — same scenario, same results.", {"size": 10.5, "color": MUTED})], "line": 1.2},
])
footer(s, 7, TOTAL)
notes(s, """TIMING 3:40–6:40 — SWITCH TO THE APP HERE.
Click order: Deliver Priya's email → Run the agents → show the impact map → Approve as organiser (business + internal scopes only) → Execute approved plan. Let the tracker retry happen. When the D3 conflict appears, stop talking and let the audience read the log. Then show plan v2, approve the 6 changed actions, execute, verify, replay 10 times.

Narration while it runs:
- "Notice the reply is a draft. The sponsor has not been emailed."
- "The tracker failed before writing, so a retry is safe. Same operation key."
- "Rohan published D3 first. Our write was refused — we did not overwrite his work. That is why this needs a replan, not a retry."
- "Plan v2 reuses four finished actions, keeps three covered, and asks approval for six changed ones."

If anything stalls: keep this slide up and use the screenshots in the appendix; do not debug on stage.""")

# ================================================================== 8. proof
s = slide_new()
kicker(s, "VERIFICATION & EVIDENCE", 8, color=TEAL)
title(s, "“The tool said OK” is not proof.")

stat(s, M, 1.78, 3.7, "21 / 21", "checks passed after execution — every changed record re-read and compared with the plan.", TEAL)
stat(s, M + 3.95, 1.78, 3.7, "0", "new effects when the same email was replayed 10 times; 13 finished actions were reused.", TEAL)
stat(s, M + 7.9, 1.78, 3.7, "78", "automated tests passed in today’s full suite run.", TEAL)
rect(s, M, 2.95, W - 2 * M, 0.012, STROKE, shape=MSO_SHAPE.RECTANGLE)

label(s, M, 3.15, 5.6, "WHAT VERIFICATION ACTUALLY CHECKS", TEAL)
bullets(s, M, 3.5, 6.05, [
    "Every field matches the approved diff, not just the API response.",
    "Money is recomputed from scratch: −₹10,000, not copied.",
    "Brightline ₹90,000 and Corvex ₹60,000 are untouched.",
    "Exactly one sponsor-review calendar item; run sheet has 3 entries.",
    "Replay produces 0 new effects — duplicates are ignored, not re-run.",
], size=11, gap=0.42, dot=TEAL)

label(s, 7.0, 3.15, 5.6, "WHAT WE HAVE NOT SOLVED", AMBER)
bullets(s, 7.0, 3.5, 5.6, [
    "Scenario suite: 20 / 24 pass, 1 fail, 3 not tested.",
    "Restart/resume and calendar fallback are not implemented.",
    "S2 long-term inheritance still fails — shown, not hidden.",
    "Gmail, chat, sheets and calendar are simulated connectors.",
], size=11, gap=0.42, dot=AMBER)

text(s, M, 6.18, 11.8, 0.45, [
    {"runs": [("A demo you can trust beats a perfect story.  ", {"size": 12.5, "bold": True, "color": TEXT}),
              ("The gaps are on the slide, not discovered in Q&A.", {"size": 12.5, "color": MUTED})], "line": 1.2},
])
footer(s, 8, TOTAL)
notes(s, """TIMING 6:40–7:30
Lead with the number: 21 checks, 0 failures, then replay 10 times, 0 duplicates. Say plainly: "We do not trust the tool's OK. We reopen every record and recompute the money."

Then the right column. Do not rush it. Judges reward teams that state limits before being asked. "20 of 24 scenarios pass; three are not tested; one known gap. Restart/resume is not built."

If asked about the failing scenario: it is the long-term-memory follow-up (S2), which starts from S1's verified end state. It is out of P0 and we report it as a failure.""")

# ================================================================== 9. architecture
s = slide_new()
kicker(s, "ARCHITECTURE", 9)
title(s, "Six narrow agents. One deterministic core.")

# coordinator
rect(s, 3.55, 1.78, 6.2, 0.62, PANEL2, INDIGO, radius=0.16, line_w=1.2)
text(s, 3.55, 1.9, 6.2, 0.3,
     [{"runs": [("COORDINATOR  ·  order, gates, retry vs replan", {"size": 10.5, "bold": True, "color": INDIGO})],
       "align": PP_ALIGN.CENTER}])
for x in (4.6, 8.7):
    rect(s, x, 2.4, 0.02, 0.42, STROKE, shape=MSO_SHAPE.RECTANGLE)

agents = [
    ("Communication", "read + extract", "Gemini optional", AMBER),
    ("Knowledge", "graph traversal", "deterministic", INDIGO),
    ("Planning", "diffs + flags", "rules", INDIGO),
    ("Human", "approval gate", "3 scopes", AMBER),
    ("Execution", "tools + retries", "versioned", INDIGO),
    ("Verification", "read back", "independent", TEAL),
]
aw = 1.79
for i, (name, job, tag, color) in enumerate(agents):
    x = M + i * (aw + 0.19)
    rect(s, x, 2.82, aw, 1.5, PANEL, color if name in ("Human", "Verification") else STROKE,
         radius=0.1, line_w=1.2 if name in ("Human", "Verification") else 0.8)
    text(s, x + 0.14, 2.96, aw - 0.2, 0.5,
         [{"runs": [(name, {"size": 11.5, "bold": True, "color": color if name in ("Human", "Verification") else TEXT})]}])
    text(s, x + 0.14, 3.35, aw - 0.24, 0.4, [{"runs": [(job, {"size": 9, "color": MUTED})]}])
    text(s, x + 0.14, 3.86, aw - 0.24, 0.3, [{"runs": [(tag, {"size": 8, "bold": True, "color": color})]}])
    if i < 5:
        text(s, x + aw - 0.03, 3.35, 0.26, 0.3, [{"runs": [("›", {"size": 13, "color": DIM})]}])

label(s, M, 4.56, 6.0, "STATE  ·  SQLITE, ONE FILE, NO HIDDEN MEMORY", MUTED)
stores = [("Versioned records", "optimistic writes"), ("Operation ledger", "idempotency keys"),
          ("Append-only log", "every agent handoff"), ("Fixture clock", "deterministic replays")]
for i, (name, sub) in enumerate(stores):
    x = M + i * 3.06
    rect(s, x, 4.86, 2.86, 0.72, PANEL, STROKE, radius=0.12)
    text(s, x + 0.18, 4.95, 2.5, 0.3, [{"runs": [(name, {"size": 10, "bold": True, "color": TEXT})]}])
    text(s, x + 0.18, 5.2, 2.5, 0.3, [{"runs": [(sub, {"size": 8.5, "color": MUTED})]}])

text(s, M, 5.85, 11.8, 0.62, [
    {"runs": [("Python 3.12 · Streamlit · SQLite · Pydantic · Gemini optional.  ",
               {"size": 11, "color": MUTED}),
              ("The model reads language; money, permissions and writes are deterministic and checked.",
               {"size": 11, "color": TEXT})], "line": 1.25},
])
text(s, M, 6.45, 11.8, 0.35, [
    {"runs": [("Why not one agent?  ", {"size": 10.5, "bold": True, "color": INDIGO}),
              ("Separate permissions, logged handoffs, and a verifier that did not do the work.",
               {"size": 10.5, "color": MUTED})]}])
footer(s, 9, TOTAL)
notes(s, """TIMING 7:30–8:20
Do not tour every box. Say: "The coordinator owns order and gates. Communication is the only place a model is genuinely in the loop, and only as a cross-check on extraction. Knowledge walks the graph. Planning is rules. Execution is versioned tool calls. Verification is independent."

Then point at the state row: records, ledger, log, fixed clock. That is the evidence trail.

Close with the split: language vs. money/permissions/writes.""")

# ================================================================== 10. close
s = slide_new()
kicker(s, "WHAT COMES NEXT", 10, color=TEAL)
title(s, "Today a prototype. Tomorrow a layer.")

rect(s, M, 1.85, 5.86, 2.95, PANEL, STROKE)
rect(s, M, 1.85, 0.05, 2.95, TEAL, shape=MSO_SHAPE.RECTANGLE)
label(s, M + 0.28, 2.0, 5.2, "BUILT AND PROVEN", TEAL)
bullets(s, M + 0.28, 2.36, 5.3, [
    "End-to-end sponsor change with real diffs",
    "Injected retry, concurrent edit, plan v2 + delta approval",
    "Read-back verification and replay with zero duplicates",
    "21 automated checks, 78 tests, working UI",
], size=10.5, gap=0.46, dot=TEAL)

rect(s, 6.82, 1.85, 5.79, 2.95, PANEL, STROKE)
rect(s, 6.82, 1.85, 0.05, 2.95, AMBER, shape=MSO_SHAPE.RECTANGLE)
label(s, 7.1, 2.0, 5.2, "NEXT, IN ORDER", AMBER)
bullets(s, 7.1, 2.36, 5.2, [
    "Live Gmail / Slack / Sheets connectors",
    "Durable checkpoints and restart-safe approvals",
    "Multi-user auth and real role scopes",
    "Long-term memory across events (S2)",
], size=10.5, gap=0.46, dot=AMBER)

rect(s, M, 5.15, W - 2 * M, 1.18, PANEL2, None, radius=0.1)
text(s, M + 0.45, 5.36, 11.3, 0.8, [
    {"runs": [("Your tools remember records. ", {"size": 20, "bold": True, "color": TEXT}),
              ("MetaVision remembers how they depend on each other.", {"size": 20, "bold": True, "color": INDIGO})],
     "line": 1.15},
])
text(s, M, 6.56, 11.8, 0.3,
     [{"runs": [("Thank you.  Questions — including the uncomfortable ones.", {"size": 11, "color": MUTED})]}])
footer(s, 10, TOTAL)
notes(s, """TIMING 8:20–9:10, then 50 seconds of buffer.
Close on the quote, not on the roadmap. Pause after it.

Invite hard questions: "We would rather be asked about the gaps now." Keep the appendix ready: safety model, scenario scorecard, likely Q&A.

If running long, cut this slide's two lists and go straight to the quote.""")

# ================================================================== backup A
s = slide_new()
kicker(s, "BACKUP  ·  SAFETY MODEL", 11, color=AMBER)
title(s, "Fail closed, ask a human, verify anyway.")

items = [
    ("Three permissions, not one", "Business records, internal notifications, and sponsor send are approved independently. A reply can be drafted without being sent."),
    ("Fail closed", "Unreadable source, failed privacy check, unknown sender: stop. No plan, no writes, no substitute from another channel."),
    ("Privacy by exclusion", "Denied sources never enter any agent context, model call, draft or message. The check runs before context is released."),
    ("Honest flags", "Irreversible work, deficits and contingent decisions go to a human. The system never invents expense cuts or extra orders."),
]
for i, (head, body) in enumerate(items):
    x = M + (i % 2) * 6.0
    y = 1.85 + (i // 2) * 2.35
    rect(s, x, y, 5.8, 2.15, PANEL, STROKE)
    rect(s, x, y, 0.05, 2.15, AMBER, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.28, y + 0.2, 5.2, 0.4, [{"runs": [(head, {"size": 14, "bold": True, "color": TEXT})]}])
    text(s, x + 0.28, y + 0.68, 5.2, 1.3, [{"runs": [(body, {"size": 11, "color": MUTED})], "line": 1.28}])
text(s, M, 6.5, 11.8, 0.35,
     [{"runs": [("Every decision and refusal is written to the append-only action log with time, agent and reason.",
                 {"size": 10.5, "color": DIM})]}])
footer(s, 11, TOTAL)
notes(s, "Backup. Use if asked how the system stays safe beyond the happy path. The strongest single line: unreadable source or failed privacy check means stop, not guess.")

# ================================================================== backup B
s = slide_new()
kicker(s, "BACKUP  ·  SCENARIO SCORECARD", 12, color=TEAL)
title(s, "24 scenarios. One honest scoreboard.")

groups = [
    ("Main demo & recoveries", "S1 approved, main demo, tracker failure, timeout-after-write, concurrent edit, replay, rejected delta", "9 / 9", TEAL),
    ("Guards & evidence", "Unknown sender, tentative, injection, privacy scope, privacy outage, gmail outage, chat mismatch, stale chat", "7 / 7", TEAL),
    ("Conflicts & clarification", "Authorized conflict, clarified, unauthorized WhatsApp, unresolved currency", "4 / 4", TEAL),
    ("Not implemented", "Restart/resume at approval, restart after sponsor commit, calendar outage fallback", "0 / 3", AMBER),
    ("Known gap", "S2 long-term inheritance from S1 (out of P0)", "0 / 1", ROSE),
]
text(s, M, 1.78, 2.85, 0.3, [{"runs": [("GROUP", {"size": 8.5, "bold": True, "color": DIM})]}])
text(s, 3.85, 1.78, 7.0, 0.3, [{"runs": [("WHAT IT COVERS", {"size": 8.5, "bold": True, "color": DIM})]}])
text(s, 11.3, 1.78, 1.4, 0.3, [{"runs": [("RESULT", {"size": 8.5, "bold": True, "color": DIM})], "align": PP_ALIGN.RIGHT}])
rect(s, M, 2.06, W - 2 * M, 0.01, STROKE, shape=MSO_SHAPE.RECTANGLE)
for i, (g, what, res, color) in enumerate(groups):
    y = 2.18 + i * 0.86
    text(s, M, y + 0.06, 2.9, 0.6, [{"runs": [(g, {"size": 10.5, "bold": True, "color": TEXT})], "line": 1.15}])
    text(s, 3.85, y + 0.04, 7.2, 0.62, [{"runs": [(what, {"size": 9.5, "color": MUTED})], "line": 1.2}])
    text(s, 11.3, y + 0.06, 1.4, 0.3, [{"runs": [(res, {"size": 10.5, "bold": True, "color": color})],
                                         "align": PP_ALIGN.RIGHT}])
    if i < 4:
        rect(s, M, y + 0.72, W - 2 * M, 0.006, STROKE, shape=MSO_SHAPE.RECTANGLE)
text(s, M, 6.55, 11.8, 0.3, [
    {"runs": [("A scenario marked “not tested” proves nothing — it is reported as untested, not as a pass.",
               {"size": 10.5, "color": DIM})]}])
footer(s, 12, TOTAL)
notes(s, "Backup. Only show if a judge challenges the test claims. The key discipline: not-tested is not a pass.")

# ================================================================== backup C
s = slide_new()
kicker(s, "BACKUP  ·  LIKELY QUESTIONS", 13, color=INDIGO)
title(s, "The five questions we expect.")

qa = [
    ("Why not let the agent just update everything?",
     "Irreversible actions and money need human judgement. We propose, a human approves, then we verify."),
    ("How do you avoid doing something twice?",
     "An operation key derived from the exact change. The ledger reuses committed keys; replay changed 0 records."),
    ("What if two people edit the same record?",
     "Optimistic versioning refuses the stale write. We re-read, replan, and ask for delta approval — never overwrite."),
    ("What if the model invents an amount?",
     "Span grounding, authority check, agreement with rules, exact-diff approval, integer recomputation, read-back."),
    ("How does this scale to real tools?",
     "Each simulated tool becomes a connector with the same contract: versioned read/write, idempotency key, reconcile on timeout."),
]
for i, (q, a) in enumerate(qa):
    y = 1.78 + i * 1.0
    rect(s, M, y, 0.05, 0.82, INDIGO, shape=MSO_SHAPE.RECTANGLE)
    text(s, M + 0.24, y - 0.02, 4.6, 0.7, [{"runs": [(q, {"size": 11, "bold": True, "color": TEXT})], "line": 1.15}])
    text(s, 5.55, y - 0.02, 7.05, 0.8, [{"runs": [(a, {"size": 10.5, "color": MUTED})], "line": 1.2}])
footer(s, 13, TOTAL)
notes(s, "Backup. Do not read these on stage. Use them during Q&A, and keep the answers to two sentences each.")

prs.save(HERE / "MetaVision.pptx")
print(f"Saved {HERE / 'MetaVision.pptx'} with {len(prs.slides.__iter__.__self__._sldIdLst)} slides")
