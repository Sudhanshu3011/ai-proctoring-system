# """
# api/v1/reports.py

# Report endpoints:
#   GET  /api/v1/reports/{session_id}           → JSON report data
#   GET  /api/v1/reports/{session_id}/download  → download PDF file
#   POST /api/v1/reports/generate/{session_id}  → manually trigger generation
  
# """

# import os
# import logging
# from fastapi import APIRouter, Depends, HTTPException
# from fastapi.responses import FileResponse , Response
# from sqlalchemy.orm import Session

# from core.security import get_current_user_payload, require_role
# from db.session    import get_db
# from db.models     import ExamSession, Violation, RiskScore, User, Exam
# from services.report_services import report_service

# logger = logging.getLogger(__name__)
# router = APIRouter(prefix="/reports", tags=["Reports"])

# REPORTS_DIR = "storage/reports"


# def _build_session_data(session_id: str, db: Session) -> dict:
#     """Pull all data needed to generate a report from the DB."""

#     session = db.query(ExamSession).filter(
#         ExamSession.id == session_id
#     ).first()
#     if not session:
#         raise HTTPException(404, "Session not found")

#     user  = db.query(User).filter(User.id == session.user_id).first()
#     exam  = db.query(Exam).filter(Exam.id == session.exam_id).first()
#     risk  = db.query(RiskScore).filter(RiskScore.session_id == session_id).first()

#     violations = db.query(Violation).filter(
#         Violation.session_id == session_id
#     ).order_by(Violation.timestamp).all()

#     # Serialize violations
#     viol_list = [
#         {
#             "timestamp"     : v.timestamp.timestamp() if v.timestamp else 0,
#             "violation_type": v.violation_type.value,
#             "source_module" : _module_from_type(v.violation_type.value),
#             "confidence"    : v.confidence or 1.0,
#             "weight"        : v.weight,
#             "duration_secs" : v.duration_secs or 0,
#             "description"   : v.description or "",
#             "screenshot"    : v.screenshot_path,
#         }
#         for v in violations
#     ]

#     # Module stats from violations
#     module_stats = {}
#     for v in viol_list:
#         mod = v["source_module"]
#         if mod not in module_stats:
#             module_stats[mod] = {
#                 "violation_count": 0,
#                 "total_weight"   : 0.0,
#                 "type_counts"    : {},
#                 "anomaly_detected": False,
#             }
#         module_stats[mod]["violation_count"] += 1
#         module_stats[mod]["total_weight"]    += v["weight"] * v["confidence"]
#         vt = v["violation_type"]
#         module_stats[mod]["type_counts"][vt] = (
#             module_stats[mod]["type_counts"].get(vt, 0) + 1
#         )

#     for mod, stats in module_stats.items():
#         if stats["type_counts"]:
#             stats["most_frequent"] = max(
#                 stats["type_counts"], key=stats["type_counts"].get
#             )
#         stats.pop("type_counts", None)

#     started   = session.started_at.timestamp()   if session.started_at   else 0
#     submitted = session.submitted_at.timestamp() if session.submitted_at else 0

#     return {
#         "session_id"       : session_id,
#         "user_name"        : user.full_name  if user  else "Unknown",
#         "user_email"       : user.email      if user  else "Unknown",
#         "exam_title"       : exam.title      if exam  else "Unknown",
#         "started_at"       : started,
#         "submitted_at"     : submitted,
#         "final_score"      : risk.current_score if risk else 0.0,
#         "peak_score"       : risk.current_score if risk else 0.0,
#         "risk_level"       : risk.risk_level.value if risk else "SAFE",
#         "cheat_probability": 0.0,
#         "total_violations" : len(viol_list),
#         "violations"       : viol_list,
#         "module_stats"     : module_stats,
#         "anomaly_flags"    : [],
#         "score_timeline"   : [],
#         "behavior_summary" : {
#             "total_violations" : len(viol_list),
#             "risk_contribution": sum(v["weight"] for v in viol_list),
#         },
#     }


# def _module_from_type(vtype: str) -> str:
#     mapping = {
#         "FACE_ABSENT":        "face",  "FACE_MISMATCH":     "face",
#         "MULTI_FACE":         "face",  "LOOKING_AWAY":      "pose",
#         "PHONE_DETECTED":     "object","BOOK_DETECTED":     "object",
#         "HEADPHONE_DETECTED": "object","SPEECH_BURST":      "audio",
#         "SUSTAINED_SPEECH":   "audio", "MULTI_SPEAKER":     "audio",
#         "WHISPER":            "audio", "TAB_SWITCH":        "browser",
#         "WINDOW_BLUR":        "browser","FULLSCREEN_EXIT":  "browser",
#         "COPY_PASTE":         "browser",
#     }
#     return mapping.get(vtype, "unknown")

# # ─────────────────────────────────────────────
# #  POST /reports/generate/{session_id}
# # ─────────────────────────────────────────────
# @router.post(
#     "/generate/{session_id}",
#     summary="Generate PDF + JSON report for a completed session",
# )
# def generate_report(
#     session_id : str,
#     token_data : dict    = Depends(get_current_user_payload),
#     db         : Session = Depends(get_db),
# ):
#     data  = _build_session_data(session_id, db)
#     paths = report_service.generate(data)
#     return {
#         "message"    : "Report generated",
#         "pdf_path"   : paths["pdf"],
#         "json_path"  : paths["json"],
#         "session_id" : session_id,
#     }


# # ─────────────────────────────────────────────
# #  GET /reports/{session_id}/download
# # ─────────────────────────────────────────────
# """
# Rules:
#   - Admin: full access — view JSON + download PDF
#   - Student: can view their OWN report JSON only — NO download
# """

# @router.get("/{session_id}", summary="Get report data (student=own only)")
# def get_report(
#     session_id : str,
#     token_data : dict    = Depends(get_current_user_payload),
#     db         : Session = Depends(get_db),
# ):
#     session = db.query(ExamSession).filter(
#         ExamSession.id == session_id
#     ).first()
#     if not session:
#         raise HTTPException(404, "Session not found")

#     # Access control — students can only see their own reports
#     role = token_data.get("role", "student")
#     if role != "admin":
#         user = db.query(User).filter(User.email == token_data["sub"]).first()
#         if not user or session.user_id != user.id:
#             raise HTTPException(403, "You can only view your own report.")

#     data = _build_session_data(session_id, db)
#     # Students don't receive the download flag
#     if role != "admin":
#         data["can_download"] = False
#     else:
#         data["can_download"] = True
#     return data

# # ─────────────────────────────────────────────
# #  GET /reports/{session_id}/download
# # ─────────────────────────────────────────────
# @router.get("/{session_id}/download", summary="Download PDF — admin only")
# def download_report(
#     session_id : str,
#     token_data : dict    = Depends(require_role("admin")),  # ← admin only
#     db         : Session = Depends(get_db),
# ):
#     pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")
#     if not os.path.exists(pdf_path):
#         try:
#             data = _build_session_data(session_id, db)
#             report_service.generate(data)
#         except Exception as e:
#             raise HTTPException(500, f"Could not generate report: {e}")

#     if not os.path.exists(pdf_path):
#         raise HTTPException(404, "Report could not be generated")

#     with open(pdf_path, 'rb') as f:
#         pdf_bytes = f.read()

#     return Response(
#         content    = pdf_bytes,
#         media_type = "application/pdf",
#         headers    = {
#             "Content-Disposition": f'attachment; filename="report_{session_id[:8]}.pdf"',
#         }
#     )



"""
api/v1/reports.py  — UPDATED

Fixes _build_session_data() to return the keys that ReportPage_pro.js
actually reads:
  candidate, exam, risk_assessment, gaze_summary, integrity_assessment

Also adds proper access control (#13):
  - Admin: can view + download PDF
  - Student: can only view their own session — no download

Report endpoints:
  GET  /api/v1/reports/{session_id}           → JSON report data
  GET  /api/v1/reports/{session_id}/download  → download PDF file
  POST /api/v1/reports/generate/{session_id}  → manually trigger generation
"""

import os
import json
import logging
from fastapi      import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.security import get_current_user_payload, require_role
from db.session    import get_db
from db.models     import (
    User, Exam, ExamSession, Violation, RiskScore,
    SessionStatus, UserRole,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Reports"])

REPORTS_DIR = os.getenv("REPORTS_DIR", "storage/reports")


# ─────────────────────────────────────────────
#  Module source map
# ─────────────────────────────────────────────
_TYPE_TO_MODULE = {
    "FACE_ABSENT":"face","FACE_MISMATCH":"face","MULTI_FACE":"face",
    "LOOKING_AWAY":"pose",
    "PHONE_DETECTED":"object","BOOK_DETECTED":"object","HEADPHONE_DETECTED":"object",
    "SPEECH_BURST":"audio","SUSTAINED_SPEECH":"audio","MULTI_SPEAKER":"audio","WHISPER":"audio",
    "TAB_SWITCH":"browser","WINDOW_BLUR":"browser","FULLSCREEN_EXIT":"browser","COPY_PASTE":"browser",
    "LIVENESS_NO_BLINK":"liveness","LIVENESS_HEAD_FROZEN":"liveness","LIVENESS_STATIC_FRAME":"liveness",
}

def _module_from_type(vtype: str) -> str:
    return _TYPE_TO_MODULE.get(vtype, "unknown")


# ─────────────────────────────────────────────
#  _build_session_data
#  Returns keys that match ReportPage_pro.js expectations exactly
# ─────────────────────────────────────────────
def _build_session_data(session_id: str, db: Session) -> dict:
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    user = db.query(User).filter(User.id == session.user_id).first()
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    risk = db.query(RiskScore).filter(RiskScore.session_id == session_id).first()

    violations = db.query(Violation).filter(
        Violation.session_id == session_id
    ).order_by(Violation.timestamp).all()

    viol_list = [
        {
            "timestamp"     : v.timestamp.timestamp() if v.timestamp else 0,
            "violation_type": v.violation_type.value  if hasattr(v.violation_type,'value') else str(v.violation_type),
            "confidence"    : float(v.confidence or 1.0),
            "weight"        : int(v.weight or 0),
            "duration_secs" : float(v.duration_secs or 0),
            "description"   : v.description or "",
        }
        for v in violations
    ]

    # Module stats
    module_stats: dict = {}
    for v in viol_list:
        mod = _module_from_type(v["violation_type"])
        if mod not in module_stats:
            module_stats[mod] = {"violation_count": 0, "total_weight": 0.0}
        module_stats[mod]["violation_count"] += 1
        module_stats[mod]["total_weight"]    += v["weight"]

    started   = session.started_at.timestamp()   if session.started_at   else 0
    submitted = session.submitted_at.timestamp() if session.submitted_at else 0
    duration  = (submitted - started) / 60.0 if submitted and started else 0

    final_score = float(risk.current_score if risk else 0.0)
    risk_level  = risk.risk_level.value    if risk else "SAFE"

    # Load integrity assessment stored on session (JSON string)
    integrity_assessment = None
    try:
        raw = getattr(session, 'integrity_assessment', None)
        if raw:
            integrity_assessment = json.loads(raw)
    except Exception:
        pass

    # Load gaze summary stored on session (JSON string)
    gaze_summary = None
    try:
        raw = getattr(session, 'gaze_summary', None)
        if raw:
            gaze_summary = json.loads(raw)
    except Exception:
        pass

    return {
        # Keys consumed by ReportPage_pro.js
        "session_id"          : session_id,
        "candidate"           : {
            "name" : user.full_name if user else "Unknown",
            "email": user.email     if user else "Unknown",
        },
        "exam"                : {
            "title"     : exam.title            if exam else "Unknown",
            "started_at": started,
            "submitted_at": submitted,
            "duration_min": round(duration, 1),
        },
        "risk_assessment"     : {
            "final_score"      : final_score,
            "risk_level"       : risk_level,
            "cheat_probability": float(risk.cheat_probability if risk and hasattr(risk,'cheat_probability') else 0.0),
            "face_score"       : float(risk.face_score    if risk else 0.0),
            "pose_score"       : float(risk.pose_score    if risk else 0.0),
            "object_score"     : float(risk.object_score  if risk else 0.0),
            "audio_score"      : float(risk.audio_score   if risk else 0.0),
            "browser_score"    : float(risk.browser_score if risk else 0.0),
        },
        "violations"          : viol_list,
        "module_stats"        : module_stats,
        "total_violations"    : len(viol_list),
        "gaze_summary"        : gaze_summary,
        "integrity_assessment": integrity_assessment,
        "can_download"        : False,  # overridden per role in endpoint
    }


# ─────────────────────────────────────────────
#  GET /reports/{session_id}
# ─────────────────────────────────────────────
@router.get(
        "/{session_id}", 
        summary="Get report (student=own only, admin=any)"
)
def get_report(
    session_id : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    role = token_data.get("role", "student")

    # Students can only view their own sessions
    if role != "admin":
        user = db.query(User).filter(User.email == token_data["sub"]).first()
        if not user or session.user_id != user.id:
            raise HTTPException(403, "You can only view your own report.")

    data = _build_session_data(session_id, db)
    data["can_download"] = (role == "admin")
    return data


# ─────────────────────────────────────────────
#  POST /reports/generate/{session_id}
# ─────────────────────────────────────────────
@router.post("/generate/{session_id}", summary="Generate PDF report")
def generate_report(
    session_id : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    role = token_data.get("role", "student")
    if role != "admin":
        # Students may trigger generation for their own session (report page)
        user    = db.query(User).filter(User.email == token_data["sub"]).first()
        session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
        if not user or not session or session.user_id != user.id:
            raise HTTPException(403, "Not authorised to generate this report.")

    try:
        from services.report_services import report_service
        data = _build_session_data(session_id, db)
        report_service.generate(data)
        return {"message": "Report generated successfully", "session_id": session_id}
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(500, f"Report generation failed: {str(e)}")


# ─────────────────────────────────────────────
#  GET /reports/{session_id}/download  (admin only)
# ─────────────────────────────────────────────
@router.get("/{session_id}/download", summary="Download PDF (admin only)")
def download_report(
    session_id : str,
    token_data : dict    = Depends(require_role("admin")),
    db         : Session = Depends(get_db),
):
    pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")

    if not os.path.exists(pdf_path):
        # Auto-generate if missing
        try:
            from services.report_services import report_service
            data = _build_session_data(session_id, db)
            report_service.generate(data)
        except Exception as e:
            raise HTTPException(500, f"Could not generate report: {e}")

    if not os.path.exists(pdf_path):
        raise HTTPException(404, "Report file not found after generation attempt.")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    return Response(
        content    = pdf_bytes,
        media_type = "application/pdf",
        headers    = {
            "Content-Disposition": f'attachment; filename="report_{session_id[:8]}.pdf"',
            "Content-Length"     : str(len(pdf_bytes)),
        },
    )