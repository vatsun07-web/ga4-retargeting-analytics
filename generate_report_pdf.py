"""
generate_report_pdf.py
----------------------
Generates a professional PDF report: reports/GA4_Report.pdf

Usage (run from your project root):
    python generate_report_pdf.py

Requires:
    pip install reportlab
"""

import subprocess, sys, json, os, io, base64, re
from datetime import date

# ── Auto-install ──────────────────────────────────────────────────────────────
def ensure(pkg):
    try:
        __import__(pkg)
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

ensure("reportlab")

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Image, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas as pdfcanvas

# ── Constants ─────────────────────────────────────────────────────────────────
NOTEBOOK_PATH = "NB-07_report.ipynb"
OUTPUT_PDF    = os.path.join("reports", "GA4_Report.pdf")

W, H          = A4                        # 595 x 842 pt
ML = MR       = 20 * mm
MT = MB       = 18 * mm
CONTENT_W     = W - ML - MR

# Brand palette
NAVY          = colors.HexColor("#0D1B2A")
ACCENT        = colors.HexColor("#1E6FBF")
ACCENT_LIGHT  = colors.HexColor("#E8F1FA")
GREEN_HL      = colors.HexColor("#D4EDDA")
GREEN_TXT     = colors.HexColor("#155724")
GREY_DARK     = colors.HexColor("#333333")
GREY_MID      = colors.HexColor("#666666")
GREY_LIGHT    = colors.HexColor("#F5F7FA")
RULE_COLOR    = colors.HexColor("#CCCCCC")
WHITE         = colors.white

# ── Styles ────────────────────────────────────────────────────────────────────
def S(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=10, leading=15,
                    textColor=GREY_DARK, spaceAfter=4, spaceBefore=0)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

STYLES = {
    "h1":       S("h1",  fontName="Helvetica-Bold", fontSize=18, textColor=NAVY,
                  spaceAfter=2, spaceBefore=14, leading=22),
    "h2":       S("h2",  fontName="Helvetica-Bold", fontSize=13, textColor=NAVY,
                  spaceAfter=4, spaceBefore=16, leading=17),
    "h3":       S("h3",  fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT,
                  spaceAfter=3, spaceBefore=10, leading=14),
    "body":     S("body", fontSize=10, leading=15, textColor=GREY_DARK,
                  spaceAfter=6, alignment=TA_JUSTIFY),
    "body_left":S("body_left", fontSize=10, leading=15, textColor=GREY_DARK, spaceAfter=6),
    "meta":     S("meta", fontSize=9,  textColor=GREY_MID, leading=13, spaceAfter=2),
    "caption":  S("caption", fontSize=9, fontName="Helvetica-Oblique",
                  textColor=GREY_MID, alignment=TA_CENTER, spaceAfter=8),
    "insight":  S("insight", fontSize=10, leading=15, textColor=GREY_DARK,
                  leftIndent=12, rightIndent=12, spaceAfter=8,
                  backColor=ACCENT_LIGHT, borderPad=6),
    "winner":   S("winner", fontSize=10, leading=15, textColor=GREEN_TXT,
                  leftIndent=12, rightIndent=12, spaceAfter=8,
                  backColor=GREEN_HL, borderPad=6),
    "bullet":   S("bullet", fontSize=10, leading=15, textColor=GREY_DARK,
                  leftIndent=14, spaceAfter=5),
    "rec_head": S("rec_head", fontName="Helvetica-Bold", fontSize=10,
                  textColor=ACCENT, spaceAfter=2, spaceBefore=8),
    "footer":   S("footer", fontSize=8, textColor=GREY_MID, alignment=TA_CENTER),
    "th":       S("th", fontName="Helvetica-Bold", fontSize=9,
                  textColor=WHITE, leading=12),
    "td":       S("td", fontSize=9, textColor=GREY_DARK, leading=12),
    "td_green": S("td_green", fontName="Helvetica-Bold", fontSize=9,
                  textColor=GREEN_TXT, leading=12),
    "toc":      S("toc", fontSize=10, textColor=WHITE, leading=16,
                  leftIndent=8),
}

# ── Helper: safe XML text ─────────────────────────────────────────────────────
def x(text):
    """Escape special chars and convert inline markdown for ReportLab XML."""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    # restore reportlab tags we insert deliberately
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`",       r'<font name="Courier" fontSize="9">\1</font>', text)
    text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
    text = text.replace("→", "->").replace("—", "-").replace("–", "-")
    text = text.replace("≥", ">=").replace("≤", "<=")
    text = text.replace("★", "*")
    return text

def P(text, style="body"):
    return Paragraph(x(text), STYLES[style])

def Sp(h=6):
    return Spacer(1, h)

def HR(color=RULE_COLOR, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness,
                      color=color, spaceAfter=6, spaceBefore=2)

# ── Custom Flowables ──────────────────────────────────────────────────────────
class ColorBox(Flowable):
    """Solid colour rectangle — used for accent bars."""
    def __init__(self, w, h, color):
        super().__init__()
        self.w, self.h, self.color = w, h, color
    def wrap(self, *args): return self.w, self.h
    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 0, self.w, self.h, fill=1, stroke=0)

class SectionDivider(Flowable):
    """Left-accented section header bar."""
    def __init__(self, text, width=CONTENT_W):
        super().__init__()
        self.text  = text
        self.width = width
        self.height = 22
    def wrap(self, *a): return self.width, self.height
    def draw(self):
        c = self.canv
        # background bar
        c.setFillColor(NAVY)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        # left accent strip
        c.setFillColor(ACCENT)
        c.rect(0, 0, 4, self.height, fill=1, stroke=0)
        # text
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(12, 6, self.text)

class KPICard(Flowable):
    """Single KPI tile."""
    def __init__(self, label, value, sub, w=None, h=62):
        super().__init__()
        self.label = label
        self.value = value
        self.sub   = sub
        self.w     = w or (CONTENT_W / 4 - 6)
        self.h     = h
    def wrap(self, *a): return self.w, self.h
    def draw(self):
        c = self.canv
        pad = 8
        # card background
        c.setFillColor(WHITE)
        c.setStrokeColor(RULE_COLOR)
        c.roundRect(0, 0, self.w, self.h, 4, fill=1, stroke=1)
        # top accent line
        c.setFillColor(ACCENT)
        c.rect(0, self.h - 4, self.w, 4, fill=1, stroke=0)
        # value
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(self.w / 2, self.h - 28, self.value)
        # label
        c.setFillColor(GREY_DARK)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(self.w / 2, self.h - 40, self.label.upper())
        # subtitle
        c.setFillColor(GREY_MID)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(self.w / 2, pad, self.sub)

# ── Page templates ────────────────────────────────────────────────────────────
class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, pagesize=A4,
                         leftMargin=ML, rightMargin=MR,
                         topMargin=MT, bottomMargin=MB, **kw)
        body_frame = Frame(ML, MB, CONTENT_W, H - MT - MB,
                           id="body", showBoundary=0)
        self.addPageTemplates([
            PageTemplate(id="Cover",   frames=[body_frame],
                         onPage=self._cover_bg),
            PageTemplate(id="TOC",     frames=[body_frame],
                         onPage=self._normal_header),
            PageTemplate(id="Content", frames=[body_frame],
                         onPage=self._normal_header),
        ])

    def _cover_bg(self, canvas, doc):
        canvas.saveState()
        # Full navy top band
        canvas.setFillColor(NAVY)
        canvas.rect(0, H * 0.52, W, H * 0.48, fill=1, stroke=0)
        # Accent stripe
        canvas.setFillColor(ACCENT)
        canvas.rect(0, H * 0.52, W, 5, fill=1, stroke=0)
        # Bottom subtle bar
        canvas.setFillColor(GREY_LIGHT)
        canvas.rect(0, 0, W, 18 * mm, fill=1, stroke=0)
        # Footer text
        canvas.setFillColor(GREY_MID)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(W / 2, 10 * mm, "CONFIDENTIAL — FOR PORTFOLIO USE ONLY")
        canvas.restoreState()

    def _normal_header(self, canvas, doc):
        canvas.saveState()
        # Thin top rule
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.5)
        canvas.line(ML, H - MT + 6, W - MR, H - MT + 6)
        # Header left
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(ML, H - MT + 9, "GA4 Google Merchandise Store")
        # Header right
        canvas.setFillColor(GREY_MID)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(W - MR, H - MT + 9,
                               "Marketing Analytics Report · May 2026")
        # Footer rule
        canvas.setStrokeColor(RULE_COLOR)
        canvas.setLineWidth(0.5)
        canvas.line(ML, MB - 6, W - MR, MB - 6)
        # Footer left
        canvas.setFillColor(GREY_MID)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(ML, MB - 14, "Seiha Vat · Data Analyst")
        # Footer right = page number
        canvas.drawRightString(W - MR, MB - 14, f"Page {doc.page}")
        canvas.restoreState()

# ── Image extractor ───────────────────────────────────────────────────────────
def png_flowable(output, max_w=CONTENT_W, max_h=None):
    max_h = max_h or H * 0.42
    b64 = output.get("data", {}).get("image/png")
    if not b64:
        return None
    if isinstance(b64, list):
        b64 = "".join(b64)
    buf = io.BytesIO(base64.b64decode(b64))
    return Image(buf, width=max_w, height=max_h, kind="proportional")

# ── Markdown table parser ─────────────────────────────────────────────────────
def md_table(rows_text, highlight_rows=None):
    """Parse markdown pipe-table lines into a ReportLab Table."""
    highlight_rows = highlight_rows or []
    data = []
    is_header = True
    for row in rows_text:
        if re.match(r"^\|[\s\-|:]+\|$", row.strip()):
            continue
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if is_header:
            data.append([Paragraph(x(c), STYLES["th"]) for c in cells])
            is_header = False
        else:
            st = "td_green" if data.index in highlight_rows else "td"
            data.append([Paragraph(x(c), STYLES["td"]) for c in cells])

    if not data:
        return None

    col_n  = len(data[0])
    col_w  = CONTENT_W / col_n
    t = Table(data, colWidths=[col_w] * col_n, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [GREY_LIGHT, WHITE]),
        ("GRID",           (0, 0), (-1, -1), 0.4, RULE_COLOR),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 7),
    ]))
    return t

# ── Model comparison table (hardcoded from notebook output) ───────────────────
def model_comparison_table():
    headers = ["Model", "ROC-AUC", "PR-AUC", "Threshold", "Precision", "Recall", "F1"]
    rows = [
        ("Logistic Regression",    "0.9942", "0.6723", "0.5000", "0.4700", "0.9856", "0.6365"),
        ("Random Forest",          "0.9958", "0.6874", "0.5000", "0.6653", "0.6680", "0.6667"),
        ("XGBoost",                "0.9960", "0.7308", "0.5000", "0.5501", "0.9969", "0.7089"),
        ("XGBoost  * optimal thr", "0.9960", "0.7308", "0.9792", "0.6200", "0.8900", "0.7315"),
    ]
    winner_rows = [3, 4]  # 0-indexed data rows (after header = row 0)

    th_style = STYLES["th"]
    td_style = STYLES["td"]
    td_win   = STYLES["td_green"]

    col_widths = [CONTENT_W * f for f in [0.24, 0.13, 0.13, 0.13, 0.13, 0.12, 0.13]]

    data = [[Paragraph(h, th_style) for h in headers]]
    for i, row in enumerate(rows):
        st = td_win if i >= 2 else td_style
        data.append([Paragraph(x(v), st) for v in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  NAVY),
        ("BACKGROUND",    (0, 3),  (-1, 4),  GREEN_HL),
        ("ROWBACKGROUNDS",(0, 1),  (-1, 2),  [GREY_LIGHT, WHITE]),
        ("GRID",          (0, 0),  (-1, -1), 0.4, RULE_COLOR),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0),  (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 5),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 6),
        ("FONTNAME",      (0, 3),  (-1, 4),  "Helvetica-Bold"),
    ]))
    return t

# ── SHAP feature table ────────────────────────────────────────────────────────
def shap_table():
    headers = ["Rank", "Feature", "Mean |SHAP|", "Business Meaning"]
    rows = [
        ("1", "checkout_starts",     "5.19", "Sessions that initiated checkout — strongest purchase signal"),
        ("2", "total_events",        "2.60", "Overall engagement breadth across the session"),
        ("3", "session_duration_sec","1.60", "Time spent on site — proxy for purchase intent"),
    ]
    col_widths = [CONTENT_W * f for f in [0.09, 0.22, 0.15, 0.54]]
    data = [[Paragraph(h, STYLES["th"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(x(v), STYLES["td"]) for v in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [GREY_LIGHT, WHITE]),
        ("GRID",           (0, 0), (-1, -1), 0.4, RULE_COLOR),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    return t

# ── Methodology table ─────────────────────────────────────────────────────────
def methodology_table():
    headers = ["Step", "Detail"]
    rows = [
        ("Data source",           "BigQuery public dataset · ga4_obfuscated_sample_ecommerce.events_*"),
        ("Extraction",            "SQL unnesting of event_params ARRAY; manual CSV download from console"),
        ("Unit of analysis",      "Session (not user)"),
        ("Target variable",       "converted = 1 if purchase event occurred in session"),
        ("Train / test split",    "80 / 20, stratified, random_state=42"),
        ("Imbalance handling",    "scale_pos_weight = 73.3 (XGBoost); class_weight=balanced (others)"),
        ("Hyperparameter tuning", "Optuna · 50 trials · XGBoost only"),
        ("Primary metric",        "PR-AUC (preferred over ROC-AUC at 1.35% positive rate)"),
        ("Explainability",        "SHAP TreeExplainer — exact values, not approximate"),
        ("Pipeline",              "NB-01 SQL → NB-02 EDA → NB-03 Features → NB-04 Models → NB-05 Funnel → NB-06 SHAP → NB-07 Report"),
    ]
    col_widths = [CONTENT_W * 0.28, CONTENT_W * 0.72]
    data = [[Paragraph(h, STYLES["th"]) for h in headers]]
    for i, row in enumerate(rows):
        bg = GREY_LIGHT if i % 2 == 0 else WHITE
        data.append([Paragraph(x(v), STYLES["td"]) for v in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [GREY_LIGHT, WHITE]),
        ("GRID",           (0, 0), (-1, -1), 0.4, RULE_COLOR),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    return t

# ── Cover page ────────────────────────────────────────────────────────────────
def cover_page():
    story = []
    story.append(Sp(H * 0.14))  # push down into the white zone below navy band

    # Logo / report type label
    story.append(Paragraph(
        '<font color="#1E6FBF">MARKETING ANALYTICS</font> &nbsp;·&nbsp; DATA SCIENCE PORTFOLIO',
        ParagraphStyle("cov_tag", fontName="Helvetica", fontSize=9,
                       textColor=GREY_MID, alignment=TA_CENTER, spaceAfter=6)))

    story.append(Sp(4))
    story.append(HR(ACCENT, 1.5))
    story.append(Sp(4))

    # Main title — in the white space
    story.append(Paragraph(
        "GA4 Google Merchandise Store",
        ParagraphStyle("cov_h1", fontName="Helvetica-Bold", fontSize=28,
                       textColor=NAVY, alignment=TA_CENTER,
                       spaceAfter=6, leading=34)))

    story.append(Paragraph(
        "Which Sessions Are Worth Retargeting?",
        ParagraphStyle("cov_sub", fontName="Helvetica", fontSize=15,
                       textColor=ACCENT, alignment=TA_CENTER,
                       spaceAfter=4, leading=20)))

    story.append(HR(RULE_COLOR))
    story.append(Sp(10))

    # Meta grid
    meta = [
        ["Prepared by",  "Seiha Vat"],
        ["Role",         "Data Analyst"],
        ["Date",         "May 13, 2026"],
        ["Dataset",      "GA4 Obfuscated Sample E-commerce · BigQuery Public Data"],
        ["Period",       "2020-11-01  →  2021-01-31  (92 days)"],
        ["Methodology",  "CRISP-DM"],
        ["Model",        "XGBoost with Optuna hyperparameter tuning"],
    ]
    def meta_row(label, value):
        return [
            Paragraph(f"<b>{label}</b>", STYLES["meta"]),
            Paragraph(value, STYLES["meta"]),
        ]
    meta_data  = [meta_row(k, v) for k, v in meta]
    meta_table = Table(meta_data, colWidths=[CONTENT_W * 0.28, CONTENT_W * 0.72])
    meta_table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("LINEBELOW",    (0, 0), (-1, -2), 0.3, RULE_COLOR),
        ("BACKGROUND",   (0, 0), (0, -1), colors.HexColor("#F0F4F8")),
    ]))
    story.append(meta_table)
    story.append(Sp(16))

    # KPI highlight strip
    story.append(HR(ACCENT, 1))
    story.append(Sp(6))
    story.append(Paragraph(
        "KEY FINDINGS AT A GLANCE",
        ParagraphStyle("kpi_label", fontName="Helvetica-Bold", fontSize=8,
                       textColor=GREY_MID, alignment=TA_CENTER, spaceAfter=8,
                       tracking=1)))

    kpi_w = (CONTENT_W - 18) / 4
    kpis  = [
        KPICard("Total Sessions",    "360,129", "Nov 2020 – Jan 2021",  kpi_w),
        KPICard("Conversion Rate",   "1.35%",   "4,848 purchases",      kpi_w),
        KPICard("Model PR-AUC",      "0.7308",  "XGBoost · test set",   kpi_w),
        KPICard("Funnel Drop-off",   "80.2%",   "view → add to cart",   kpi_w),
    ]
    kpi_row = Table([[k for k in kpis]],
                    colWidths=[kpi_w] * 4,
                    hAlign="CENTER")
    kpi_row.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
    ]))
    story.append(kpi_row)
    story.append(Sp(14))
    story.append(HR(ACCENT, 1))

    story.append(PageBreak())
    return story

# ── Table of Contents ─────────────────────────────────────────────────────────
def toc_page():
    story = []
    story.append(Sp(8))
    story.append(SectionDivider("TABLE OF CONTENTS"))
    story.append(Sp(12))

    sections = [
        ("1",  "Key Metrics"),
        ("2",  "Purchase Funnel Analysis"),
        ("3",  "Cohort Retention"),
        ("4",  "Model Comparison"),
        ("5",  "SHAP Explainability — What Drives Conversion?"),
        ("6",  "Actionable Recommendations"),
        ("7",  "Limitations & Future Work"),
        ("8",  "Methodology"),
    ]
    toc_data = []
    for num, title in sections:
        toc_data.append([
            Paragraph(f"<b>{num}.</b>", STYLES["toc"]),
            Paragraph(title, STYLES["toc"]),
            Paragraph("· · · · · · · · · · · · · · · ·",
                      ParagraphStyle("dots", fontSize=10,
                                     textColor=RULE_COLOR, alignment=TA_RIGHT)),
        ])
    toc_t = Table(toc_data, colWidths=[CONTENT_W * 0.07,
                                        CONTENT_W * 0.70,
                                        CONTENT_W * 0.23])
    toc_t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",   (0, 0), (-1, -1), 0.3, RULE_COLOR),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0,0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(toc_t)
    story.append(PageBreak())
    return story

# ── Build main content ────────────────────────────────────────────────────────
def build_content(nb):
    cells   = nb["cells"]
    story   = []

    # ── Section 1: Key Metrics ────────────────────────────────────────────────
    story.append(SectionDivider("1.  KEY METRICS"))
    story.append(Sp(10))

    kpi_w = (CONTENT_W - 18) / 4
    kpis  = [
        KPICard("Total Sessions",    "360,129", "GA4 · Nov 2020 – Jan 2021", kpi_w),
        KPICard("Conversion Rate",   "1.35%",   "4,848 converting sessions", kpi_w),
        KPICard("Model PR-AUC",      "0.7308",  "XGBoost · test set",        kpi_w),
        KPICard("Top Traffic Source","Organic", "Highest-volume medium",      kpi_w),
    ]
    kpi_row = Table([[k for k in kpis]], colWidths=[kpi_w] * 4, hAlign="CENTER")
    kpi_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(kpi_row)
    story.append(Sp(14))

    # Sub KPIs row 2 — model detail
    sub_kpis = [
        ("Optimal Threshold",  "0.9792",  "Maximises F1 on test set"),
        ("Recall @ Threshold", "89%",     "True converters captured"),
        ("Precision",          "62%",     "Of flagged sessions convert"),
        ("Imbalance Ratio",    "73.3 : 1","Non-converters per converter"),
    ]
    sub_data = [[
        Paragraph(f'<b><font color="#1E6FBF">{v}</font></b><br/>'
                  f'<font size="8" color="#666">{l}</font><br/>'
                  f'<font size="7" color="#999">{s}</font>',
                  ParagraphStyle("sub_kpi", alignment=TA_CENTER,
                                 leading=14, spaceAfter=0))
        for l, v, s in sub_kpis
    ]]
    sub_t = Table(sub_data, colWidths=[CONTENT_W / 4] * 4)
    sub_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GREY_LIGHT),
        ("GRID",          (0, 0), (-1, -1), 0.4, RULE_COLOR),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sub_t)
    story.append(Sp(8))

    # ── Section 2: Purchase Funnel ────────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionDivider("2.  PURCHASE FUNNEL ANALYSIS"))
    story.append(Sp(10))

    # funnel image from cell 5
    img_cell = cells[5]
    for out in img_cell.get("outputs", []):
        img = png_flowable(out, max_w=CONTENT_W, max_h=210)
        if img:
            story.append(img)
            story.append(Paragraph("Figure 1 — Purchase funnel: sessions at each stage",
                                   STYLES["caption"]))

    story.append(KeepTogether([
        Paragraph(
            '<b>Key Insight:</b> The largest single drop-off in the purchase funnel '
            'occurs between <font name="Courier" fontSize="9">view_item</font> and '
            '<font name="Courier" fontSize="9">add_to_cart</font> — <b>80.2% of sessions '
            'that viewed a product did not add it to their cart.</b> This represents the '
            'highest-volume retargeting audience: users who demonstrated product interest '
            'but stopped short of cart commitment.',
            STYLES["insight"]),
    ]))

    # ── Section 3: Cohort Retention ───────────────────────────────────────────
    story.append(Sp(8))
    story.append(SectionDivider("3.  COHORT RETENTION"))
    story.append(Sp(10))

    img_cell = cells[8]
    for out in img_cell.get("outputs", []):
        img = png_flowable(out, max_w=CONTENT_W, max_h=210)
        if img:
            story.append(img)
            story.append(Paragraph("Figure 2 — Weekly cohort retention heatmap",
                                   STYLES["caption"]))

    story.append(KeepTogether([
        Paragraph(
            '<b>Key Insight:</b> Average week-1 return rate is <b>4.8%</b> — below the '
            '10-20% benchmark typical of engaged e-commerce audiences. This signals a '
            'meaningful opportunity for re-engagement campaigns targeting users in the '
            '7-14 day window after their first session.',
            STYLES["insight"]),
        Sp(4),
        Paragraph(
            'Note: The dataset covers 92 days, yielding 13 weekly cohorts with a maximum '
            'of ~12 weeks of follow-up for the earliest cohort. Retention beyond week 8 '
            'is sparse and should be interpreted with caution.',
            STYLES["meta"]),
    ]))

    # ── Section 4: Model Comparison ───────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionDivider("4.  MODEL COMPARISON"))
    story.append(Sp(10))

    story.append(P(
        "Three models were trained representing different learning paradigms. "
        "PR-AUC was used as the primary evaluation metric because the dataset is heavily "
        "imbalanced (1.35% positive rate), making ROC-AUC an unreliable guide to "
        "real-world performance.", "body"))
    story.append(Sp(6))
    story.append(model_comparison_table())
    story.append(Paragraph("Table 1 — Model comparison on held-out test set. "
                            "Green rows = XGBoost winner.", STYLES["caption"]))
    story.append(Sp(6))

    story.append(KeepTogether([
        Paragraph(
            '<b>Winner: XGBoost (Optuna-tuned)</b> — XGBoost achieved a PR-AUC of '
            '<b>0.7308</b>, outperforming Random Forest (0.6874) by 0.0434, above the '
            '0.03 materiality threshold. At the optimal threshold of <b>0.9792</b>, the '
            'model achieves <b>89% recall</b> on converters at a precision of 62%, '
            'capturing the vast majority of true purchasers while keeping the false '
            'positive rate manageable.',
            STYLES["winner"]),
    ]))

    # ── Section 5: SHAP Explainability ───────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionDivider("5.  SHAP EXPLAINABILITY — WHAT DRIVES CONVERSION?"))
    story.append(Sp(10))

    story.append(P(
        "SHAP (SHapley Additive exPlanations) values decompose each prediction into "
        "the contribution of each feature. The beeswarm plot below shows every test-set "
        "session as a dot; position on the x-axis is the SHAP value (contribution to "
        "prediction); colour indicates feature value — red = high, blue = low.", "body"))
    story.append(Sp(6))

    img_cell = cells[14]
    for out in img_cell.get("outputs", []):
        img = png_flowable(out, max_w=CONTENT_W, max_h=230)
        if img:
            story.append(img)
            story.append(Paragraph("Figure 3 — SHAP beeswarm plot: global feature importance",
                                   STYLES["caption"]))

    story.append(Sp(6))
    story.append(shap_table())
    story.append(Paragraph("Table 2 — Top 3 SHAP features by mean absolute value",
                            STYLES["caption"]))
    story.append(Sp(6))

    story.append(KeepTogether([
        Paragraph(
            '<font name="Courier" fontSize="9">checkout_starts</font> dominates by a wide '
            'margin (mean |SHAP| = <b>5.19</b>). In practical terms, the model is a '
            'sophisticated checkout-abandonment detector with engagement signals layered '
            'on top. A session that reached checkout but did not purchase is the '
            'single strongest retargeting signal available.',
            STYLES["insight"]),
    ]))

    # ── Section 6: Recommendations ───────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionDivider("6.  ACTIONABLE RECOMMENDATIONS"))
    story.append(Sp(10))

    recs = [
        (
            "01  |  Prioritise Checkout Abandoners for Retargeting",
            "Sessions with checkout_starts >= 1 that did not purchase are the highest-intent "
            "audience available. These users crossed the psychological barrier of entering "
            "checkout. A time-sensitive retargeting message — abandoned cart reminder "
            "within 24 hours — applied exclusively to this segment will deliver the highest "
            "conversion uplift per unit of media spend.",
            "Impact: High  ·  Effort: Low  ·  Audience: ~1,384 predicted converters/period"
        ),
        (
            "02  |  Apply an Engagement Threshold Before Retargeting",
            "total_events is the second-strongest conversion signal (mean |SHAP| = 2.60). "
            "Sessions in the bottom quartile of total engagement are predicted as "
            "non-converters with high confidence. Excluding low-engagement sessions from "
            "retargeting audiences reduces wasted spend without meaningfully cutting reach "
            "among likely converters.",
            "Impact: Medium  ·  Effort: Low  ·  Audience: All retargeting lists"
        ),
        (
            "03  |  Re-engagement Campaign in the 7-14 Day Window",
            "The cohort analysis shows a week-1 return rate of 4.8% — well below the "
            "10-20% benchmark for engaged e-commerce users. A structured re-engagement "
            "email or display campaign targeting users 7-14 days after their first session "
            "represents a low-cost, high-potential lever for improving retention.",
            "Impact: Medium  ·  Effort: Medium  ·  Audience: All week-1 non-returners"
        ),
    ]

    for title, body_text, impact in recs:
        story.append(KeepTogether([
            Paragraph(title, STYLES["rec_head"]),
            Paragraph(body_text, STYLES["body"]),
            Paragraph(f"<i>{impact}</i>", STYLES["meta"]),
            Sp(4),
            HR(),
        ]))

    # ── Section 7: Limitations ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionDivider("7.  LIMITATIONS & FUTURE WORK"))
    story.append(Sp(10))

    limits = [
        ("Fixed 92-day window",
         "The dataset covers exactly 2020-11-01 to 2021-01-31 — the only data "
         "available in the public BigQuery dataset. The window cannot be extended."),
        ("Seasonality not analysable",
         "The 92-day window spans Black Friday, Christmas, and New Year — making it "
         "inherently non-representative of typical traffic. Seasonality analysis is "
         "out of scope."),
        ("Shallow cohort retention",
         "92 days yields ~13 weekly cohorts; the earliest cohort has at most ~12 weeks "
         "of follow-up. Retention beyond week 8 is sparse and near-empty for later "
         "cohorts."),
        ("Obfuscated data",
         "Certain fields contain placeholder values (<Other>, data deleted, empty string). "
         "Internal consistency is limited by design; some distributions may be "
         "unreliable."),
        ("Session-level only",
         "The model scores sessions, not users. A user visiting multiple times may appear "
         "in both training and test sets across different sessions."),
    ]

    for title, text in limits:
        story.append(Paragraph(f"<b>{title}:</b>  {x(text)}", STYLES["body"]))
        story.append(HR())

    story.append(Sp(8))
    story.append(P("**Future Work**", "h3"))
    future = [
        "Extend to 12+ months of data to enable true seasonality analysis",
        "Build user-level propensity scores to avoid session-level data leakage",
        "Incorporate product-category signals from item-level event parameters",
        "Validate model performance against a prospective holdout window",
        "Deploy as a real-time scoring API integrated with Google Ads audience lists",
    ]
    for item in future:
        story.append(Paragraph(f"&bull; &nbsp; {x(item)}", STYLES["bullet"]))

    # ── Section 8: Methodology ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionDivider("8.  METHODOLOGY"))
    story.append(Sp(10))
    story.append(methodology_table())
    story.append(Paragraph("Table 3 — Project methodology summary", STYLES["caption"]))

    return story

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # locate notebook
    nb_path = NOTEBOOK_PATH
    if not os.path.exists(nb_path):
        alt = os.path.join("notebooks", NOTEBOOK_PATH)
        if os.path.exists(alt):
            nb_path = alt
        else:
            print(f"ERROR: Cannot find {nb_path}")
            sys.exit(1)

    print(f"Reading   {nb_path}")
    with open(nb_path, encoding="utf-8") as f:
        nb = json.load(f)

    os.makedirs("reports", exist_ok=True)

    doc   = ReportDoc(OUTPUT_PDF)
    story = []

    # Page 1 — Cover (uses Cover template)
    story += cover_page()

    # Page 2 — TOC (switches to TOC template)
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate("TOC"))
    story += toc_page()

    # Remaining pages — Content template
    story.append(NextPageTemplate("Content"))
    story += build_content(nb)

    doc.build(story)

    size_kb = os.path.getsize(OUTPUT_PDF) / 1024
    print(f"Done.  {size_kb:.0f} KB  ->  {OUTPUT_PDF}")
    print("Open with:  open reports/GA4_Report.pdf")

if __name__ == "__main__":
    main()
