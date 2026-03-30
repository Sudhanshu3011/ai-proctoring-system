"""
api/v1/reports.py

Report endpoints:
  GET  /api/v1/reports/{session_id}           → JSON report data
  GET  /api/v1/reports/{session_id}/download  → download PDF file
  POST /api/v1/reports/generate/{session_id}  → manually trigger generation
"""

import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse , Response
from sqlalchemy.orm import Session

from core.security import get_current_user_payload, require_role
from db.session    import get_db
from db.models     import ExamSession, Violation, RiskScore, User, Exam
from services.report_services import report_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Reports"])

REPORTS_DIR = "storage/reports"


def _build_session_data(session_id: str, db: Session) -> dict:
    """Pull all data needed to generate a report from the DB."""

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    user  = db.query(User).filter(User.id == session.user_id).first()
    exam  = db.query(Exam).filter(Exam.id == session.exam_id).first()
    risk  = db.query(RiskScore).filter(RiskScore.session_id == session_id).first()

    violations = db.query(Violation).filter(
        Violation.session_id == session_id
    ).order_by(Violation.timestamp).all()

    # Serialize violations
    viol_list = [
        {
            "timestamp"     : v.timestamp.timestamp() if v.timestamp else 0,
            "violation_type": v.violation_type.value,
            "source_module" : _module_from_type(v.violation_type.value),
            "confidence"    : v.confidence or 1.0,
            "weight"        : v.weight,
            "duration_secs" : v.duration_secs or 0,
            "description"   : v.description or "",
            "screenshot"    : v.screenshot_path,
        }
        for v in violations
    ]

    # Module stats from violations
    module_stats = {}
    for v in viol_list:
        mod = v["source_module"]
        if mod not in module_stats:
            module_stats[mod] = {
                "violation_count": 0,
                "total_weight"   : 0.0,
                "type_counts"    : {},
                "anomaly_detected": False,
            }
        module_stats[mod]["violation_count"] += 1
        module_stats[mod]["total_weight"]    += v["weight"] * v["confidence"]
        vt = v["violation_type"]
        module_stats[mod]["type_counts"][vt] = (
            module_stats[mod]["type_counts"].get(vt, 0) + 1
        )

    for mod, stats in module_stats.items():
        if stats["type_counts"]:
            stats["most_frequent"] = max(
                stats["type_counts"], key=stats["type_counts"].get
            )
        stats.pop("type_counts", None)

    started   = session.started_at.timestamp()   if session.started_at   else 0
    submitted = session.submitted_at.timestamp() if session.submitted_at else 0

    return {
        "session_id"       : session_id,
        "user_name"        : user.full_name  if user  else "Unknown",
        "user_email"       : user.email      if user  else "Unknown",
        "exam_title"       : exam.title      if exam  else "Unknown",
        "started_at"       : started,
        "submitted_at"     : submitted,
        "final_score"      : risk.current_score if risk else 0.0,
        "peak_score"       : risk.current_score if risk else 0.0,
        "risk_level"       : risk.risk_level.value if risk else "SAFE",
        "cheat_probability": 0.0,
        "total_violations" : len(viol_list),
        "violations"       : viol_list,
        "module_stats"     : module_stats,
        "anomaly_flags"    : [],
        "score_timeline"   : [],
        "behavior_summary" : {
            "total_violations" : len(viol_list),
            "risk_contribution": sum(v["weight"] for v in viol_list),
        },
    }


def _module_from_type(vtype: str) -> str:
    mapping = {
        "FACE_ABSENT":        "face",  "FACE_MISMATCH":     "face",
        "MULTI_FACE":         "face",  "LOOKING_AWAY":      "pose",
        "PHONE_DETECTED":     "object","BOOK_DETECTED":     "object",
        "HEADPHONE_DETECTED": "object","SPEECH_BURST":      "audio",
        "SUSTAINED_SPEECH":   "audio", "MULTI_SPEAKER":     "audio",
        "WHISPER":            "audio", "TAB_SWITCH":        "browser",
        "WINDOW_BLUR":        "browser","FULLSCREEN_EXIT":  "browser",
        "COPY_PASTE":         "browser",
    }
    return mapping.get(vtype, "unknown")


# ─────────────────────────────────────────────
#  GET /reports/{session_id}
# ─────────────────────────────────────────────
@router.get("/{session_id}", summary="Get report data as JSON")
def get_report(
    session_id : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    return _build_session_data(session_id, db)


# ─────────────────────────────────────────────
#  POST /reports/generate/{session_id}
# ─────────────────────────────────────────────
@router.post(
    "/generate/{session_id}",
    summary="Generate PDF + JSON report for a completed session",
)
def generate_report(
    session_id : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    data  = _build_session_data(session_id, db)
    paths = report_service.generate(data)
    return {
        "message"    : "Report generated",
        "pdf_path"   : paths["pdf"],
        "json_path"  : paths["json"],
        "session_id" : session_id,
    }


# ─────────────────────────────────────────────
#  GET /reports/{session_id}/download
# ─────────────────────────────────────────────
# @router.get(
#     "/{session_id}/download",
#     summary="Download PDF report",
# )
# def download_report(
#     session_id : str,
#     token_data : dict    = Depends(get_current_user_payload),
#     db         : Session = Depends(get_db),
# ):
#     pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")

#     # Auto-generate if not exists
#     if not os.path.exists(pdf_path):
#         data = _build_session_data(session_id, db)
#         report_service.generate(data)

#     if not os.path.exists(pdf_path):
#         raise HTTPException(404, "Report could not be generated")

#     return FileResponse(
#         path         = pdf_path,
#         media_type   = "application/pdf",
#         filename     = f"proctor_report_{session_id[:8]}.pdf",
#     )


@router.get("/{session_id}/download", summary="Download PDF report")
def download_report(
    session_id : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")

    # Auto-generate if not exists
    if not os.path.exists(pdf_path):
        try:
            data = _build_session_data(session_id, db)
            report_service.generate(data)
        except Exception as e:
            raise HTTPException(500, f"Could not generate report: {e}")

    if not os.path.exists(pdf_path):
        raise HTTPException(404, "Report file not found even after generation attempt")

    # Read file and return as bytes — avoids FileResponse path issues
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()

    return Response(
        content     = pdf_bytes,
        media_type  = "application/pdf",
        headers     = {
            "Content-Disposition": f'attachment; filename="proctor_report_{session_id[:8]}.pdf"',
            "Content-Length"     : str(len(pdf_bytes)),
        }
    )

