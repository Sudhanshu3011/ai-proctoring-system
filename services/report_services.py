"""
services/report_service.py

Exam Report Generation Service

Generates a detailed post-exam PDF + JSON report containing:
    - Candidate details and exam info
    - Final risk score and cheating probability
    - Violation timeline (every event, timestamped)
    - Per-module breakdown (face, pose, object, audio, browser)
    - Behavior anomaly flags
    - Screenshot evidence gallery
    - Risk score graph (score over time)

Output formats:
    - PDF  → storage/reports/{session_id}.pdf   (for admin download)
    - JSON → storage/reports/{session_id}.json  (for API / archival)

Libraries:
    - reportlab   → PDF generation
    - matplotlib  → score timeline graph embedded in PDF

Called by:
    api/v1/exam.py     → after submit or terminate
    api/v1/reports.py  → GET /reports/{session_id}/download
"""

import os
import json
import time
import logging
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ReportLab
from reportlab.lib.pagesizes   import A4
from reportlab.lib.styles      import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units       import cm
from reportlab.lib             import colors
from reportlab.platypus        import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether,
)
from reportlab.lib.enums       import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics        import renderPDF

# Matplotlib for score graph
import matplotlib
matplotlib.use("Agg")   # non-interactive backend — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from io import BytesIO

from ai_engine.logger import get_logger

logger = get_logger("report_service")

# ─────────────────────────────────────────────
#  Paths
# ─────────────────────────────────────────────
REPORTS_DIR = Path("storage/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
#  Colour palette
# ─────────────────────────────────────────────
C_DARK      = colors.HexColor("#1a1a2e")
C_PRIMARY   = colors.HexColor("#16213e")
C_ACCENT    = colors.HexColor("#0f3460")
C_SAFE      = colors.HexColor("#2ecc71")
C_WARNING   = colors.HexColor("#f39c12")
C_HIGH      = colors.HexColor("#e67e22")
C_CRITICAL  = colors.HexColor("#e74c3c")
C_WHITE     = colors.white
C_LIGHT     = colors.HexColor("#ecf0f1")
C_MID       = colors.HexColor("#bdc3c7")
C_TEXT      = colors.HexColor("#2c3e50")
C_SUBTEXT   = colors.HexColor("#7f8c8d")

LEVEL_COLORS = {
    "SAFE"    : C_SAFE,
    "WARNING" : C_WARNING,
    "HIGH"    : C_HIGH,
    "CRITICAL": C_CRITICAL,
}


# ─────────────────────────────────────────────
#  Helper: risk level colour
# ─────────────────────────────────────────────
def _level_color(level: str):
    return LEVEL_COLORS.get(level, C_MID)


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S UTC")


def _fmt_dt(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%d %b %Y  %H:%M:%S UTC"
    )


def _elapsed(start: float, end: float) -> str:
    secs = int(end - start)
    m, s = divmod(secs, 60)
    return f"{m}m {s}s"


# ─────────────────────────────────────────────
#  Score timeline graph  (matplotlib → BytesIO → ReportLab Image)
# ─────────────────────────────────────────────
def _build_score_graph(timeline: list[dict]) -> Optional[BytesIO]:
    """
    Renders a risk score over time chart.
    Returns a BytesIO PNG buffer suitable for embedding in ReportLab.
    Returns None if timeline is empty.
    """
    if not timeline:
        return None

    try:
        times  = [i * 5 for i in range(len(timeline))]   # every 5s
        scores = [t.get("score", 0) for t in timeline]
        levels = [t.get("level", "SAFE") for t in timeline]

        fig, ax = plt.subplots(figsize=(14, 3.5))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#16213e")

        # Threshold bands
        ax.axhspan(0,  30, alpha=0.08, color="#2ecc71")
        ax.axhspan(30, 60, alpha=0.08, color="#f39c12")
        ax.axhspan(60, 85, alpha=0.08, color="#e67e22")
        ax.axhspan(85,100, alpha=0.08, color="#e74c3c")

        # Threshold lines
        for y, lbl, col in [
            (30, "Warning", "#f39c12"),
            (60, "High",    "#e67e22"),
            (85, "Critical","#e74c3c"),
        ]:
            ax.axhline(y, color=col, linewidth=0.8, linestyle="--", alpha=0.6)
            ax.text(times[-1] + 1, y, lbl, color=col, fontsize=7, va="center")

        # Score line — colour segments by level
        level_color_map = {
            "SAFE"    : "#2ecc71",
            "WARNING" : "#f39c12",
            "HIGH"    : "#e67e22",
            "CRITICAL": "#e74c3c",
        }
        for i in range(len(times) - 1):
            col = level_color_map.get(levels[i], "#bdc3c7")
            ax.plot(
                times[i:i+2], scores[i:i+2],
                color=col, linewidth=2.0, solid_capstyle="round"
            )

        # Fill under the line
        ax.fill_between(times, scores, alpha=0.12, color="#3498db")

        # Axes styling
        ax.set_xlim(0, max(times) + 5)
        ax.set_ylim(0, 105)
        ax.set_xlabel("Time (seconds)", color="#bdc3c7", fontsize=9)
        ax.set_ylabel("Risk Score",     color="#bdc3c7", fontsize=9)
        ax.tick_params(colors="#bdc3c7", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#0f3460")
        ax.grid(color="#0f3460", linewidth=0.5, alpha=0.5)

        plt.tight_layout(pad=0.5)

        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=130,
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception as e:
        logger.error(f"Score graph generation failed: {e}")
        return None


# ─────────────────────────────────────────────
#  ReportService
# ─────────────────────────────────────────────
class ReportService:
    """
    Generates PDF and JSON exam reports.

    Usage:
        service = ReportService()
        paths   = service.generate(session_data)
        # paths = {"pdf": "storage/reports/xxx.pdf",
        #          "json": "storage/reports/xxx.json"}
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._register_styles()

    # ─────────────────────────────────────────
    #  Custom paragraph styles
    # ─────────────────────────────────────────
    def _register_styles(self):
        add = self.styles.add

        add(ParagraphStyle(
            "ReportTitle",
            parent    = self.styles["Title"],
            fontSize  = 26, textColor = C_WHITE,
            spaceAfter = 4, alignment = TA_CENTER,
            fontName  = "Helvetica-Bold",
        ))
        add(ParagraphStyle(
            "ReportSubtitle",
            parent   = self.styles["Normal"],
            fontSize = 11, textColor = C_MID,
            alignment= TA_CENTER, spaceAfter = 2,
        ))
        add(ParagraphStyle(
            "SectionHeader",
            parent    = self.styles["Heading2"],
            fontSize  = 13, textColor = C_WHITE,
            spaceBefore=14, spaceAfter=6,
            fontName  = "Helvetica-Bold",
        ))
        add(ParagraphStyle(
            "FieldLabel",
            parent   = self.styles["Normal"],
            fontSize = 9, textColor = C_SUBTEXT,
            spaceAfter= 1,
        ))
        add(ParagraphStyle(
            "FieldValue",
            parent   = self.styles["Normal"],
            fontSize = 11, textColor = C_TEXT,
            spaceAfter= 6,
        ))
        add(ParagraphStyle(
            "ViolationText",
            parent   = self.styles["Normal"],
            fontSize = 8.5, textColor = C_TEXT,
            leading  = 14,
        ))
        add(ParagraphStyle(
            "SmallGray",
            parent   = self.styles["Normal"],
            fontSize = 8, textColor = C_SUBTEXT,
        ))

    # ─────────────────────────────────────────
    #  Public entry point
    # ─────────────────────────────────────────
    def generate(self, session_data: dict) -> dict[str, str]:
        """
        Generate PDF and JSON reports for a completed exam session.

        Args:
            session_data: dict with keys —
                session_id, user_name, user_email, exam_title,
                started_at (float), submitted_at (float),
                final_score (float), risk_level (str),
                cheat_probability (float),
                violations (list of dicts),
                module_stats (dict),
                anomaly_flags (list),
                score_timeline (list of dicts),
                behavior_summary (dict),
                face_summary (dict),

        Returns:
            {"pdf": "<path>", "json": "<path>"}
        """
        sid = session_data.get("session_id", "unknown")
        logger.info(f"Generating report | session={sid}")

        pdf_path  = str(REPORTS_DIR / f"{sid}.pdf")
        json_path = str(REPORTS_DIR / f"{sid}.json")

        try:
            self._generate_pdf(session_data, pdf_path)
            self._generate_json(session_data, json_path)
            logger.info(f"Report generated | pdf={pdf_path}")
            return {"pdf": pdf_path, "json": json_path}
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            raise

    # ─────────────────────────────────────────
    #  JSON report
    # ─────────────────────────────────────────
    def _generate_json(self, data: dict, path: str):
        """Write structured JSON report — for API serving and archival."""
        report = {
            "report_generated_at" : datetime.now(timezone.utc).isoformat(),
            "session_id"          : data.get("session_id"),
            "candidate"           : {
                "name" : data.get("user_name"),
                "email": data.get("user_email"),
            },
            "exam"                : {
                "title"           : data.get("exam_title"),
                "started_at"      : data.get("started_at"),
                "submitted_at"    : data.get("submitted_at"),
                "duration_seconds": (
                    (data.get("submitted_at", 0) or 0)
                    - (data.get("started_at",  0) or 0)
                ),
            },
            "risk_assessment"     : {
                "final_score"      : data.get("final_score"),
                "risk_level"       : data.get("risk_level"),
                "cheat_probability": data.get("cheat_probability"),
                "peak_score"       : data.get("peak_score", 0),
            },
            "module_stats"        : data.get("module_stats", {}),
            "anomaly_flags"       : data.get("anomaly_flags", []),
            "violations"          : data.get("violations",    []),
            "score_timeline"      : data.get("score_timeline",[]),
            "behavior_summary"    : data.get("behavior_summary", {}),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

    # ─────────────────────────────────────────
    #  PDF report
    # ─────────────────────────────────────────
    def _generate_pdf(self, data: dict, path: str):
        """Build a multi-section PDF report using ReportLab Platypus."""
        doc = SimpleDocTemplate(
            path,
            pagesize     = A4,
            leftMargin   = 2.0 * cm,
            rightMargin  = 2.0 * cm,
            topMargin    = 2.0 * cm,
            bottomMargin = 2.0 * cm,
        )

        story = []

        # ── Cover block ───────────────────────────────────────────
        story += self._build_cover(data)
        story.append(Spacer(1, 0.5 * cm))

        # ── Risk summary cards ────────────────────────────────────
        story += self._build_risk_summary(data)
        story.append(Spacer(1, 0.4 * cm))

        # ── Score timeline graph ──────────────────────────────────
        story += self._build_score_section(data)
        story.append(Spacer(1, 0.4 * cm))

        # ── Module breakdown ──────────────────────────────────────
        story += self._build_module_breakdown(data)
        story.append(Spacer(1, 0.4 * cm))

        # ── Anomaly flags ─────────────────────────────────────────
        story += self._build_anomaly_section(data)
        story.append(Spacer(1, 0.4 * cm))

        # ── Violation timeline ────────────────────────────────────
        story += self._build_violation_timeline(data)
        story.append(Spacer(1, 0.4 * cm))

        # ── Footer note ───────────────────────────────────────────
        story += self._build_footer(data)

        # Build with dark background per page
        doc.build(
            story,
            onFirstPage = self._page_background,
            onLaterPages= self._page_background,
        )

    def _page_background(self, canvas, doc):
        """Draw dark background on every page."""
        canvas.saveState()
        canvas.setFillColor(C_DARK)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        # Subtle header bar
        canvas.setFillColor(C_PRIMARY)
        canvas.rect(0, A4[1] - 1.2 * cm, A4[0], 1.2 * cm, fill=1, stroke=0)
        # Page number
        canvas.setFillColor(C_SUBTEXT)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            A4[0] - 1.5 * cm, 0.6 * cm,
            f"Page {doc.page}  |  AI Proctoring System — Confidential"
        )
        canvas.restoreState()

    # ─────────────────────────────────────────
    #  Section builders
    # ─────────────────────────────────────────
    def _build_cover(self, data: dict) -> list:
        s = self.styles
        elems = []

        elems.append(Spacer(1, 0.6 * cm))
        elems.append(Paragraph(
            "AI EXAM PROCTORING REPORT", s["ReportTitle"]
        ))
        elems.append(Paragraph(
            f"Confidential — {datetime.now(timezone.utc).strftime('%d %B %Y')}",
            s["ReportSubtitle"],
        ))
        elems.append(HRFlowable(
            width="100%", thickness=1,
            color=C_ACCENT, spaceAfter=12,
        ))

        # Two-column info table
        started   = data.get("started_at",   0) or 0
        submitted = data.get("submitted_at", 0) or 0
        level     = data.get("risk_level", "SAFE")

        info_data = [
            ["Candidate",    data.get("user_name",  "—"),
             "Session ID",   str(data.get("session_id","—"))[:16] + "..."],
            ["Email",        data.get("user_email", "—"),
             "Exam",         data.get("exam_title", "—")],
            ["Started",      _fmt_dt(started) if started else "—",
             "Submitted",    _fmt_dt(submitted) if submitted else "—"],
            ["Duration",     _elapsed(started, submitted) if started else "—",
             "Risk Level",   level],
        ]

        col_w = [3.2*cm, 6.0*cm, 3.2*cm, 5.6*cm]
        tbl   = Table(info_data, colWidths=col_w, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME",  (2,0), (2,-1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0,0), (0,-1), C_SUBTEXT),
            ("TEXTCOLOR", (2,0), (2,-1), C_SUBTEXT),
            ("TEXTCOLOR", (1,0), (1,-1), C_WHITE),
            ("TEXTCOLOR", (3,0), (3,-1), C_WHITE),
            # Highlight risk level cell
            ("TEXTCOLOR", (3,3), (3,3),  _level_color(level)),
            ("FONTNAME",  (3,3), (3,3),  "Helvetica-Bold"),
            ("FONTSIZE",  (3,3), (3,3),  11),
            ("ROWBACKGROUNDS", (0,0), (-1,-1),
             [colors.HexColor("#16213e"), colors.HexColor("#1a2744")]),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        elems.append(tbl)
        return elems

    def _build_risk_summary(self, data: dict) -> list:
        s      = self.styles
        score  = data.get("final_score",       0.0)
        level  = data.get("risk_level",        "SAFE")
        prob   = data.get("cheat_probability", 0.0)
        peak   = data.get("peak_score",        0.0)
        total  = data.get("total_violations",  0)

        elems  = []
        elems.append(Paragraph("Risk Assessment", s["SectionHeader"]))

        card_data = [[
            self._score_cell(score, level),
            self._stat_cell("Cheat Probability", f"{prob*100:.1f}%",
                            C_CRITICAL if prob > 0.75 else C_WARNING if prob > 0.4 else C_SAFE),
            self._stat_cell("Peak Score",  f"{peak:.1f}", _level_color(level)),
            self._stat_cell("Violations",  str(total),    C_WARNING),
        ]]
        tbl = Table(card_data, colWidths=[4.5*cm, 4.5*cm, 4.0*cm, 4.0*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,-1), C_PRIMARY),
            ("BOX",         (0,0), (-1,-1), 1, C_ACCENT),
            ("INNERGRID",   (0,0), (-1,-1), 0.5, C_ACCENT),
            ("ALIGN",       (0,0), (-1,-1), "CENTER"),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",  (0,0), (-1,-1), 12),
            ("BOTTOMPADDING",(0,0),(-1,-1), 12),
        ]))
        elems.append(tbl)
        return elems

    def _score_cell(self, score: float, level: str):
        col   = _level_color(level)
        style = ParagraphStyle(
            "SC", fontSize=30, textColor=col,
            alignment=TA_CENTER, fontName="Helvetica-Bold",
        )
        lbl   = ParagraphStyle(
            "SL", fontSize=9, textColor=C_SUBTEXT, alignment=TA_CENTER,
        )
        from reportlab.platypus import KeepInFrame
        return [
            Paragraph(f"{score:.1f}", style),
            Paragraph("Final Score / 100", lbl),
        ]

    def _stat_cell(self, label: str, value: str, color):
        vp = ParagraphStyle(
            f"SV{label}", fontSize=20, textColor=color,
            alignment=TA_CENTER, fontName="Helvetica-Bold",
        )
        lp = ParagraphStyle(
            f"SL{label}", fontSize=8.5, textColor=C_SUBTEXT,
            alignment=TA_CENTER,
        )
        return [Paragraph(value, vp), Paragraph(label, lp)]

    def _build_score_section(self, data: dict) -> list:
        s      = self.styles
        elems  = []
        timeline = data.get("score_timeline", [])

        elems.append(Paragraph("Risk Score Timeline", s["SectionHeader"]))

        buf = _build_score_graph(timeline)
        if buf:
            img = RLImage(buf, width=17*cm, height=4.2*cm)
            elems.append(img)
        else:
            elems.append(Paragraph(
                "No score timeline data available.", s["SmallGray"]
            ))
        return elems

    def _build_module_breakdown(self, data: dict) -> list:
        s      = self.styles
        stats  = data.get("module_stats", {})
        elems  = []

        elems.append(Paragraph("Module Breakdown", s["SectionHeader"]))

        if not stats:
            elems.append(Paragraph("No module data.", s["SmallGray"]))
            return elems

        rows   = [["Module", "Violations", "Risk Weight", "Top Violation", "Anomaly"]]
        for mod, st in stats.items():
            anomaly = "YES" if st.get("anomaly_detected") else "—"
            rows.append([
                mod.upper(),
                str(st.get("violation_count", 0)),
                f"{st.get('total_weight', 0):.1f}",
                st.get("most_frequent", "—"),
                anomaly,
            ])

        tbl = Table(rows, colWidths=[3*cm, 3*cm, 3.5*cm, 6*cm, 2.5*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0),  C_ACCENT),
            ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
            ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("TEXTCOLOR",   (0,1), (-1,-1), C_WHITE),
            ("ROWBACKGROUNDS", (0,1),(-1,-1),
             [C_PRIMARY, colors.HexColor("#1a2744")]),
            ("ALIGN",       (1,0), (-1,-1), "CENTER"),
            ("TOPPADDING",  (0,0), (-1,-1), 6),
            ("BOTTOMPADDING",(0,0),(-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("GRID",        (0,0), (-1,-1), 0.4, C_ACCENT),
            # Highlight YES anomaly cells
            *[("TEXTCOLOR",  (4, i+1), (4, i+1), C_CRITICAL)
              for i, row in enumerate(rows[1:]) if row[4] == "YES"],
        ]))
        elems.append(tbl)
        return elems

    def _build_anomaly_section(self, data: dict) -> list:
        s      = self.styles
        flags  = data.get("anomaly_flags", [])
        elems  = []

        elems.append(Paragraph("Detected Anomaly Patterns", s["SectionHeader"]))

        if not flags:
            elems.append(Paragraph(
                "No behavioral anomaly patterns detected.", s["SmallGray"]
            ))
            return elems

        sev_colors = {
            "CRITICAL": C_CRITICAL, "HIGH": C_HIGH,
            "MEDIUM":   C_WARNING,  "LOW":  C_SAFE,
        }

        rows = [["Severity", "Type", "Description", "Multiplier"]]
        for f in flags:
            rows.append([
                f.get("severity",    "—"),
                f.get("flag_type",   "—"),
                textwrap.shorten(f.get("description", "—"), width=60),
                f"{f.get('multiplier', 1.0):.1f}×",
            ])

        tbl = Table(rows, colWidths=[2.5*cm, 3.5*cm, 9*cm, 3*cm])
        style_cmds = [
            ("BACKGROUND",  (0,0), (-1,0),  C_ACCENT),
            ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
            ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 8.5),
            ("TEXTCOLOR",   (0,1), (-1,-1), C_WHITE),
            ("ROWBACKGROUNDS", (0,1),(-1,-1),
             [C_PRIMARY, colors.HexColor("#1a2744")]),
            ("TOPPADDING",  (0,0), (-1,-1), 6),
            ("BOTTOMPADDING",(0,0),(-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("GRID",        (0,0), (-1,-1), 0.4, C_ACCENT),
        ]
        for i, row in enumerate(rows[1:], start=1):
            col = sev_colors.get(row[0], C_MID)
            style_cmds.append(("TEXTCOLOR", (0,i), (0,i), col))
            style_cmds.append(("FONTNAME",  (0,i), (0,i), "Helvetica-Bold"))

        tbl.setStyle(TableStyle(style_cmds))
        elems.append(tbl)
        return elems

    def _build_violation_timeline(self, data: dict) -> list:
        s          = self.styles
        violations = data.get("violations", [])
        started_at = data.get("started_at", 0) or 0
        elems      = []

        elems.append(Paragraph(
            f"Violation Timeline  ({len(violations)} events)",
            s["SectionHeader"],
        ))

        if not violations:
            elems.append(Paragraph("No violations recorded.", s["SmallGray"]))
            return elems

        rows = [["Time", "Type", "Module", "Confidence", "Weight", "Duration"]]
        for v in violations:
            ts      = v.get("timestamp", 0) or 0
            elapsed = f"+{int(ts - started_at)}s" if started_at else _fmt_time(ts)
            rows.append([
                elapsed,
                v.get("violation_type", "—"),
                v.get("source_module",  "—").upper(),
                f"{v.get('confidence', 0)*100:.0f}%",
                str(v.get("weight", 0)),
                f"{v.get('duration_secs', 0):.1f}s"
                if v.get("duration_secs") else "—",
            ])

        # Chunk into pages of 25 rows each
        chunk_size = 25
        for chunk_start in range(0, len(rows), chunk_size):
            chunk = [rows[0]] + rows[chunk_start+1: chunk_start+1+chunk_size] \
                    if chunk_start > 0 else rows[:chunk_size+1]

            tbl = Table(
                chunk,
                colWidths=[2.0*cm, 5.0*cm, 2.8*cm, 2.5*cm, 2.0*cm, 2.7*cm],
            )
            high_weight_rows = [
                i+1 for i, row in enumerate(chunk[1:])
                if int(row[4]) >= 30
            ]
            style_cmds = [
                ("BACKGROUND",  (0,0), (-1,0),  C_ACCENT),
                ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
                ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",    (0,0), (-1,-1), 8),
                ("TEXTCOLOR",   (0,1), (-1,-1), C_WHITE),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),
                 [C_PRIMARY, colors.HexColor("#1a2744")]),
                ("TOPPADDING",  (0,0), (-1,-1), 4),
                ("BOTTOMPADDING",(0,0),(-1,-1), 4),
                ("LEFTPADDING", (0,0), (-1,-1), 6),
                ("GRID",        (0,0), (-1,-1), 0.3, C_ACCENT),
            ]
            for r in high_weight_rows:
                style_cmds.append(
                    ("BACKGROUND", (0,r), (-1,r), colors.HexColor("#3d1a1a"))
                )
            tbl.setStyle(TableStyle(style_cmds))
            elems.append(tbl)
            elems.append(Spacer(1, 0.2*cm))

        return elems

    def _build_footer(self, data: dict) -> list:
        s     = self.styles
        elems = []
        elems.append(HRFlowable(
            width="100%", thickness=0.5,
            color=C_ACCENT, spaceBefore=10,
        ))
        elems.append(Paragraph(
            "This report was automatically generated by the AI-Based Intelligent "
            "Online Exam Proctoring System. All detections are based on AI model "
            "outputs and should be reviewed by a human invigilator before any "
            "disciplinary action is taken. Report is confidential.",
            s["SmallGray"],
        ))
        return elems


# ─────────────────────────────────────────────
#  Module-level singleton
#  from services.report_service import report_service
# ─────────────────────────────────────────────
report_service = ReportService()


# ─────────────────────────────────────────────
#  Standalone test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import random

    print("\n── ReportService standalone test ─────────────────────")

    now   = time.time()
    start = now - 3600   # 1 hour exam

    # Build fake session data
    viol_types = [
        "LOOKING_AWAY","TAB_SWITCH","SPEECH_BURST",
        "PHONE_DETECTED","FACE_ABSENT","MULTI_SPEAKER",
    ]
    violations = []
    for i in range(35):
        vt = random.choice(viol_types)
        violations.append({
            "timestamp"     : start + random.randint(60, 3500),
            "violation_type": vt,
            "source_module" : {"LOOKING_AWAY":"pose","TAB_SWITCH":"browser",
                               "SPEECH_BURST":"audio","PHONE_DETECTED":"object",
                               "FACE_ABSENT":"face","MULTI_SPEAKER":"audio"
                               }.get(vt,"face"),
            "confidence"    : round(random.uniform(0.7, 0.99), 2),
            "weight"        : random.choice([10,15,20,30,40]),
            "duration_secs" : round(random.uniform(0, 5), 1),
        })
    violations.sort(key=lambda x: x["timestamp"])

    timeline = [
        {"score": min(100, 5 + i * 2.5 + random.uniform(-3, 5)),
         "level": "SAFE" if i < 10 else "WARNING" if i < 20 else "HIGH",
         "timestamp": start + i * 5}
        for i in range(40)
    ]

    session_data = {
        "session_id"       : "test-session-12345678",
        "user_name"        : "Sudhanshu Sharma",
        "user_email"       : "sudhanshu@example.com",
        "exam_title"       : "Python Fundamentals — Midterm",
        "started_at"       : start,
        "submitted_at"     : now,
        "final_score"      : 72.4,
        "peak_score"       : 88.1,
        "risk_level"       : "HIGH",
        "cheat_probability": 0.81,
        "total_violations" : len(violations),
        "violations"       : violations,
        "score_timeline"   : timeline,
        "module_stats"     : {
            "face"   : {"violation_count":8,  "total_weight":80.0,  "most_frequent":"FACE_ABSENT",    "anomaly_detected":False},
            "pose"   : {"violation_count":15, "total_weight":225.0, "most_frequent":"LOOKING_AWAY",   "anomaly_detected":True},
            "object" : {"violation_count":3,  "total_weight":120.0, "most_frequent":"PHONE_DETECTED", "anomaly_detected":True},
            "audio"  : {"violation_count":6,  "total_weight":100.0, "most_frequent":"SPEECH_BURST",   "anomaly_detected":False},
            "browser": {"violation_count":3,  "total_weight":60.0,  "most_frequent":"TAB_SWITCH",     "anomaly_detected":False},
        },
        "anomaly_flags"    : [
            {"severity":"HIGH",    "flag_type":"COOCCURRENCE",
             "description":"Phone + speech detected together in 30s window",
             "multiplier":2.0},
            {"severity":"MEDIUM",  "flag_type":"FREQUENCY",
             "description":"LOOKING_AWAY occurred 15x (threshold=10)",
             "multiplier":1.5},
        ],
        "behavior_summary" : {"total_violations":35, "risk_contribution":585},
    }

    svc   = ReportService()
    paths = svc.generate(session_data)
    print(f"\n  PDF  → {paths['pdf']}")
    print(f"  JSON → {paths['json']}")
    print(f"\n  PDF size  : {os.path.getsize(paths['pdf'])  // 1024} KB")
    print(f"  JSON size : {os.path.getsize(paths['json']) // 1024} KB")
    print("\n  Open the PDF to verify output.")
    print("──────────────────────────────────────────────────────\n")