"""
generate_exec_summary.py
------------------------
Generates a single-page professional executive summary PDF.
Output: reports/GA4_Executive_Summary.pdf

Usage (run from your project root):
    python generate_exec_summary.py

Requires:
    pip install reportlab
"""

import subprocess, sys, os

def ensure(pkg):
    try:
        __import__(pkg)
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

ensure("reportlab")

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas as pdfcanvas

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_PDF = os.path.join("reports", "GA4_Executive_Summary.pdf")

# ── Page geometry ─────────────────────────────────────────────────────────────
W, H   = A4
ML = MR = 16 * mm
MT     = 52 * mm   # leave room for the hand-drawn header
MB     = 22 * mm
CW     = W - ML - MR

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY        = colors.HexColor("#0D1B2A")
ACCENT      = colors.HexColor("#1E6FBF")
ACCENT_PALE = colors.HexColor("#EBF3FC")
GREEN       = colors.HexColor("#1A7F4B")
GREEN_BG    = colors.HexColor("#EAF6EF")
AMBER       = colors.HexColor("#B45309")
AMBER_BG    = colors.HexColor("#FEF3C7")
GREY_DARK   = colors.HexColor("#222222")
GREY_MID    = colors.HexColor("#555555")
GREY_LIGHT  = colors.HexColor("#F4F6F9")
RULE        = colors.HexColor("#CCCCCC")
WHITE       = colors.white

# ── Style factory ─────────────────────────────────────────────────────────────
def S(name, **kw):
    base = dict(fontName="Helvetica", fontSize=9, leading=13,
                textColor=GREY_DARK, spaceAfter=0, spaceBefore=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

ST = {
    "section":  S("section", fontName="Helvetica-Bold", fontSize=7.5,
                  textColor=ACCENT, tracking=0.5),
    "body":     S("body",    fontSize=8.8, leading=13.5,
                  textColor=GREY_DARK, alignment=TA_JUSTIFY),
    "body_l":   S("body_l",  fontSize=8.8, leading=13.5, textColor=GREY_DARK),
    "bullet":   S("bullet",  fontSize=8.8, leading=13.5,
                  textColor=GREY_DARK, leftIndent=10),
    "kpi_val":  S("kpi_val", fontName="Helvetica-Bold", fontSize=19,
                  textColor=NAVY,  alignment=TA_CENTER, leading=22),
    "kpi_lbl":  S("kpi_lbl", fontName="Helvetica-Bold", fontSize=7,
                  textColor=GREY_MID, alignment=TA_CENTER, leading=10),
    "kpi_sub":  S("kpi_sub", fontSize=6.8, textColor=GREY_MID,
                  alignment=TA_CENTER, leading=9),
    "rec_no":   S("rec_no",  fontName="Helvetica-Bold", fontSize=8.5,
                  textColor=ACCENT),
    "rec_body": S("rec_body", fontSize=8.5, leading=13, textColor=GREY_DARK),
    "finding":  S("finding",  fontSize=8.5, leading=13, textColor=GREY_DARK,
                  leftIndent=8),
    "footer":   S("footer",   fontSize=7, textColor=GREY_MID,
                  alignment=TA_CENTER, leading=10),
    "tag":      S("tag", fontName="Helvetica-Bold", fontSize=7,
                  textColor=WHITE, alignment=TA_CENTER),
}

def x(t):
    """Escape and convert simple inline markdown for ReportLab."""
    import re
    t = str(t)
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font name="Courier" fontSize="8">\1</font>', t)
    t = t.replace("→", "->").replace("—", "-").replace("–", "-")
    t = t.replace("≥", ">=")
    return t

def P(text, style="body"):
    return Paragraph(x(text), ST[style])

def Sp(h=4):
    return Spacer(1, h)

def HR(color=RULE, t=0.5, before=3, after=3):
    return HRFlowable(width="100%", thickness=t, color=color,
                      spaceBefore=before, spaceAfter=after)

# ── Custom flowables ──────────────────────────────────────────────────────────
class HeaderBand(Flowable):
    """Full-width header drawn directly on the canvas above the frame."""
    pass   # drawn via onFirstPage below

class SectionLabel(Flowable):
    """Uppercase coloured section label with left accent bar."""
    def __init__(self, text, width=CW):
        super().__init__()
        self.text  = text.upper()
        self.width = width
        self.height = 14
    def wrap(self, *a): return self.width, self.height
    def draw(self):
        c = self.canv
        c.setFillColor(ACCENT)
        c.rect(0, 2, 3, self.height - 2, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(8, 4, self.text)

class KPIBlock(Flowable):
    """Single KPI tile with top accent, value, label, sub-label."""
    def __init__(self, value, label, sub, accent=ACCENT, w=None, h=52):
        super().__init__()
        self.value  = value
        self.label  = label
        self.sub    = sub
        self.accent = accent
        self.w      = w or ((CW - 15) / 5)
        self.h      = h
    def wrap(self, *a): return self.w, self.h
    def draw(self):
        c = self.canv
        # card
        c.setFillColor(WHITE)
        c.setStrokeColor(RULE)
        c.roundRect(0, 0, self.w, self.h, 3, fill=1, stroke=1)
        # accent top bar
        c.setFillColor(self.accent)
        c.rect(0, self.h - 3.5, self.w, 3.5, fill=1, stroke=0)
        # value
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(self.w / 2, self.h - 22, self.value)
        # label
        c.setFillColor(GREY_MID)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(self.w / 2, self.h - 32, self.label.upper())
        # sub
        c.setFillColor(GREY_MID)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(self.w / 2, 5, self.sub)

class PillTag(Flowable):
    """Coloured pill badge — used for impact/effort labels."""
    def __init__(self, text, bg=ACCENT, fg=WHITE, w=60, h=13):
        super().__init__()
        self.text = text
        self.bg   = bg
        self.fg   = fg
        self.w    = w
        self.h    = h
    def wrap(self, *a): return self.w, self.h
    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.roundRect(0, 0, self.w, self.h, self.h / 2, fill=1, stroke=0)
        c.setFillColor(self.fg)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(self.w / 2, 3.2, self.text.upper())

# ── Canvas callbacks ──────────────────────────────────────────────────────────
def draw_header(canvas, doc):
    canvas.saveState()

    # ── Navy top bar ──────────────────────────────────────────────────────────
    bar_h = 38 * mm
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - bar_h, W, bar_h, fill=1, stroke=0)

    # Accent left strip
    canvas.setFillColor(ACCENT)
    canvas.rect(0, H - bar_h, 5, bar_h, fill=1, stroke=0)

    # Decorative right circle
    canvas.setFillColor(colors.HexColor("#162840"))
    canvas.circle(W - 18*mm, H - bar_h/2, 22*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#1A3050"))
    canvas.circle(W - 10*mm, H - bar_h + 5*mm, 14*mm, fill=1, stroke=0)

    # Report type tag
    canvas.setFillColor(ACCENT)
    canvas.roundRect(ML, H - 10*mm, 52*mm, 5.5*mm, 2, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(ML + 3*mm, H - 7.2*mm, "EXECUTIVE SUMMARY  ·  DATA SCIENCE PROJECT")

    # Main title
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 17)
    canvas.drawString(ML, H - 18*mm, "GA4 Google Merchandise Store")

    # Subtitle
    canvas.setFillColor(colors.HexColor("#A8C4E0"))
    canvas.setFont("Helvetica", 10)
    canvas.drawString(ML, H - 24.5*mm, "Which Sessions Are Worth Retargeting?  —  Conversion Propensity Model")

    # Meta line
    canvas.setFillColor(colors.HexColor("#7A9FBF"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(ML, H - 30*mm,
        "Seiha Vat  ·  Data Analyst  ·  May 2026  ·  BigQuery GA4 · Nov 2020 – Jan 2021 (92 days)  ·  CRISP-DM")

    # ── Thin accent divider below header ─────────────────────────────────────
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1)
    canvas.line(0, H - bar_h, W, H - bar_h)

    # ── Footer ────────────────────────────────────────────────────────────────
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, W, 14*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#A8C4E0"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(ML, 5.5*mm,
        "Seiha Vat  ·  Data Analyst  ·  Portfolio Project — For Illustrative Purposes")
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawRightString(W - MR, 5.5*mm,
        "Full report: reports/GA4_Report.pdf")

    canvas.restoreState()

# ── Build story ───────────────────────────────────────────────────────────────
def build():
    os.makedirs("reports", exist_ok=True)

    doc = SimpleDocTemplate(
        OUTPUT_PDF,
        pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB,
        title="GA4 Executive Summary — Seiha Vat",
        author="Seiha Vat",
        subject="Conversion Propensity Model — Google Merchandise Store",
    )

    story = []

    # ── KPI strip ─────────────────────────────────────────────────────────────
    kpi_w  = (CW - 16) / 5
    kpis   = [
        KPIBlock("360,129", "Sessions Analysed", "Nov 2020 – Jan 2021",   ACCENT,  kpi_w),
        KPIBlock("1.35%",   "Conversion Rate",   "4,848 purchases",       ACCENT,  kpi_w),
        KPIBlock("0.7308",  "Model Accuracy",    "PR-AUC · XGBoost",      GREEN,   kpi_w),
        KPIBlock("89%",     "Buyers Captured",   "Recall at threshold",   GREEN,   kpi_w),
        KPIBlock("80.2%",   "Funnel Drop-off",   "View → Add to Cart",    AMBER,   kpi_w),
    ]
    kpi_row = Table(
        [[k for k in kpis]],
        colWidths=[kpi_w] * 5,
        hAlign="LEFT"
    )
    kpi_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0), (-1,-1), 2),
        ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ]))
    story.append(kpi_row)
    story.append(Sp(8))
    story.append(HR(RULE, 0.4))
    story.append(Sp(5))

    # ── Three-column layout: Context | Findings | Recommendations ─────────────
    col_w   = [CW * 0.30, CW * 0.38, CW * 0.30]
    gap     = 2 * mm

    # ── Column 1: Context & Approach ─────────────────────────────────────────
    c1 = [
        SectionLabel("Context & Approach"),
        Sp(5),
        P("The Google Merchandise Store receives hundreds of thousands of "
          "sessions per quarter, yet fewer than **2 in every 100** result in "
          "a purchase. Retargeting every session wastes budget; retargeting "
          "none leaves revenue on the table.", "body"),
        Sp(5),
        P("This project builds a **conversion propensity model** — a machine "
          "learning tool that scores each session by its likelihood to purchase, "
          "so the marketing team can focus spend where it matters.", "body"),
        Sp(7),
        SectionLabel("What Was Built"),
        Sp(5),
        P("**Dataset:** 360,129 sessions from BigQuery's public GA4 dataset, "
          "covering 92 days of real e-commerce traffic.", "body"),
        Sp(3),
        P("**Approach:** Three models were trained and compared — Logistic "
          "Regression (baseline), Random Forest, and XGBoost. XGBoost won.", "body"),
        Sp(3),
        P("**Validation:** Models were evaluated on a held-out 20% test set "
          "using PR-AUC — the correct metric for heavily imbalanced data.", "body"),
        Sp(7),
        SectionLabel("Why PR-AUC, Not Accuracy?"),
        Sp(5),
        P("Only 1.35% of sessions convert. A model that predicts "
          "'no purchase' for every session would be 98.65% accurate — "
          "and completely useless. PR-AUC measures performance specifically "
          "on the minority class that matters: buyers.", "body"),
    ]

    # ── Column 2: Key Findings ────────────────────────────────────────────────
    findings_data = [
        ("Purchase Funnel",
         "80.2% of sessions that viewed a product **never added it to cart**. "
         "This is the largest single drop-off and the biggest retargeting audience."),
        ("Checkout Abandonment",
         "Sessions that started checkout but did not purchase are the "
         "**#1 conversion signal** — the model flags these with near-certainty."),
        ("Low Return Rate",
         "Only **4.8%** of users return within one week of their first visit — "
         "well below the 10–20% e-commerce benchmark."),
        ("Model Performance",
         "XGBoost captures **89% of all true buyers** in the test set, "
         "while keeping false positives manageable at 62% precision."),
    ]

    c2 = [
        SectionLabel("Key Findings"),
        Sp(5),
    ]
    for title, text in findings_data:
        c2 += [
            Paragraph(
                f'<font color="#0D1B2A"><b>{x(title)}</b></font>',
                ST["body_l"]),
            Sp(2),
            P(text, "body"),
            Sp(4),
            HR(RULE, 0.3, 0, 4),
        ]

    c2 += [
        Sp(2),
        SectionLabel("Top Conversion Drivers"),
        Sp(5),
    ]

    drivers = [
        ("#1", "checkout_starts",      "Initiated checkout — strongest signal by far"),
        ("#2", "total_events",         "High session engagement breadth"),
        ("#3", "session_duration_sec", "Time on site — proxy for intent"),
    ]
    for rank, feat, desc in drivers:
        c2.append(Table(
            [[
                Paragraph(f"<b>{rank}</b>",
                          ParagraphStyle("rk", fontName="Helvetica-Bold",
                                         fontSize=8, textColor=ACCENT,
                                         alignment=TA_CENTER)),
                Paragraph(
                    f'<font name="Courier" size="8"><b>{feat}</b></font><br/>'
                    f'<font size="7.5" color="#555">{desc}</font>',
                    ParagraphStyle("drv", fontSize=8, leading=12)),
            ]],
            colWidths=[col_w[1]*0.12, col_w[1]*0.88],
        ))
        c2.append(Sp(4))

    # ── Column 3: Recommendations ─────────────────────────────────────────────
    recs = [
        (
            "01  Target Checkout Abandoners",
            "Users who started checkout but did not buy are your highest-intent "
            "audience. An abandoned-cart reminder within **24 hours** will deliver "
            "the highest return on retargeting spend.",
            "HIGH IMPACT", GREEN_BG, GREEN,
        ),
        (
            "02  Filter Low-Engagement Sessions",
            "Sessions with very few page interactions are predicted as "
            "non-converters with high confidence. **Exclude them** from retargeting "
            "lists to reduce wasted spend without losing real buyers.",
            "QUICK WIN", ACCENT_PALE, ACCENT,
        ),
        (
            "03  Re-engage at Day 7–14",
            "With only 4.8% of users returning in week one, a structured "
            "re-engagement email or display campaign in the **7–14 day window** "
            "is a low-cost lever to improve retention.",
            "MEDIUM IMPACT", AMBER_BG, AMBER,
        ),
    ]

    c3 = [
        SectionLabel("Recommendations"),
        Sp(5),
    ]
    for title, text, tag, tag_bg, tag_fg in recs:
        c3 += [
            Table(
                [[
                    Paragraph(f"<b>{x(title)}</b>",
                              ParagraphStyle("rh", fontName="Helvetica-Bold",
                                             fontSize=8.5, textColor=NAVY,
                                             leading=12)),
                    Paragraph(
                        tag,
                        ParagraphStyle("rtag", fontName="Helvetica-Bold",
                                       fontSize=6.5, textColor=tag_fg,
                                       alignment=TA_RIGHT)),
                ]],
                colWidths=[col_w[2]*0.65, col_w[2]*0.35],
            ),
            Sp(3),
            P(text, "body"),
            Sp(3),
            HR(tag_fg, 0.8, 0, 6),
        ]

    c3 += [
        Sp(2),
        SectionLabel("Skills Demonstrated"),
        Sp(5),
    ]
    skills = [
        "BigQuery SQL  ·  GA4 event schema",
        "Feature engineering  ·  Class imbalance",
        "XGBoost  ·  Optuna tuning  ·  PR-AUC",
        "SHAP explainability  ·  CRISP-DM",
        "Python · pandas · scikit-learn",
    ]
    for s in skills:
        c3.append(Paragraph(f"&bull; &nbsp; {s}",
                            ParagraphStyle("sk", fontSize=8, leading=13,
                                           textColor=GREY_MID, leftIndent=6)))

    # ── Assemble three-column table ───────────────────────────────────────────
    def pad_col(col):
        """Wrap a column list in a single-cell table so padding works."""
        t = Table([[c] for c in col], colWidths=[col_w[0]])
        t.setStyle(TableStyle([
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        return t

    three_col = Table(
        [[c1, c2, c3]],
        colWidths=[col_w[0], col_w[1] + gap, col_w[2]],
        hAlign="LEFT",
    )
    three_col.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (0,-1),  5),
        ("RIGHTPADDING", (1,0), (1,-1),  8),
        ("RIGHTPADDING", (2,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ("LINEBEFORE",   (1,0), (1,-1),  0.4, RULE),
        ("LINEBEFORE",   (2,0), (2,-1),  0.4, RULE),
        ("LEFTPADDING",  (1,0), (1,-1),  8),
        ("LEFTPADDING",  (2,0), (2,-1),  8),
    ]))

    story.append(three_col)

    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header)
    size_kb = os.path.getsize(OUTPUT_PDF) / 1024
    print(f"Done.  {size_kb:.0f} KB  ->  {OUTPUT_PDF}")
    print("Open:   open reports/GA4_Executive_Summary.pdf")

if __name__ == "__main__":
    build()
