"""
api/v1/reports.py — FINAL

Changes:
  1. Email fully removed — no SMTP dependency
  2. _build_session_data() computes integrity assessment on-the-fly
     if not stored on session (handles older sessions)
  3. Returns score_timeline for admin chart
  4. Student access: view-only, can_download always False
  5. Admin access: full data + can_download True + download endpoint
"""

import os
import json
import math
import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.security import get_current_user_payload, require_role
from db.session import get_db
from db.models import (
    User,
    Exam,
    ExamSession,
    Violation,
    RiskScore,
    SessionStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Reports"])

REPORTS_DIR = os.getenv("REPORTS_DIR", "storage/reports")

_TYPE_TO_MODULE = {
    "FACE_ABSENT": "face",
    "FACE_MISMATCH": "face",
    "MULTI_FACE": "face",
    "LOOKING_AWAY": "pose",
    "PHONE_DETECTED": "object",
    "BOOK_DETECTED": "object",
    "HEADPHONE_DETECTED": "object",
    "SPEECH_BURST": "audio",
    "SUSTAINED_SPEECH": "audio",
    "MULTI_SPEAKER": "audio",
    "WHISPER": "audio",
    "TAB_SWITCH": "browser",
    "WINDOW_BLUR": "browser",
    "FULLSCREEN_EXIT": "browser",
    "COPY_PASTE": "browser",
    "LIVENESS_NO_BLINK": "liveness",
    "LIVENESS_HEAD_FROZEN": "liveness",
    "LIVENESS_STATIC_FRAME": "liveness",
}


def _module_from_type(vt: str) -> str:
    return _TYPE_TO_MODULE.get(vt, "unknown")


def _build_session_data(session_id: str, db: Session) -> dict:
    """
    Pulls all report data from DB.
    Computes integrity assessment on-the-fly if not previously stored.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    user = db.query(User).filter(User.id == session.user_id).first()
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    risk = db.query(RiskScore).filter(RiskScore.session_id == session_id).first()

    violations = (
        db.query(Violation)
        .filter(Violation.session_id == session_id)
        .order_by(Violation.timestamp)
        .all()
    )

    # ── Serialise violations ──────────────────────────────────────
    viol_list = []
    for v in violations:
        vt = (
            v.violation_type.value
            if hasattr(v.violation_type, "value")
            else str(v.violation_type)
        )
        viol_list.append(
            {
                "timestamp": v.timestamp.timestamp() if v.timestamp else 0.0,
                "violation_type": vt,
                "source_module": _module_from_type(vt),
                "confidence": float(v.confidence or 1.0),
                "weight": int(v.weight or 0),
                "duration_secs": float(v.duration_secs or 0.0),
                "description": v.description or "",
            }
        )

    # ── Module stats ──────────────────────────────────────────────
    module_stats: dict = {}
    for v in viol_list:
        mod = v["source_module"]
        if mod not in module_stats:
            module_stats[mod] = {"violation_count": 0, "total_weight": 0.0}
        module_stats[mod]["violation_count"] += 1
        module_stats[mod]["total_weight"] += v["weight"]

    # ── Timestamps ───────────────────────────────────────────────
    started = session.started_at.timestamp() if session.started_at else 0.0
    submitted = session.submitted_at.timestamp() if session.submitted_at else 0.0
    duration = (submitted - started) / 60.0 if submitted and started else 0.0

    final_score = float(risk.current_score if risk else 0.0)
    risk_level = risk.risk_level.value if risk else "SAFE"

    # ── Cheat probability (cumulative — computed from violations) ─
    # Using the same formula as integrity_scorer so values agree.
    total_weight = sum(v["weight"] for v in viol_list)
    combined_signal = (total_weight / max(1.0, duration * 10.0)) + (final_score * 0.3)
    k = 0.10
    cheat_prob = float(1.0 / (1.0 + math.exp(-k * (combined_signal - 40))))

    # ── Risk assessment ───────────────────────────────────────────
    risk_assessment = {
        "final_score": float(round(final_score, 1)),
        "risk_level": risk_level,
        "cheat_probability": float(round(cheat_prob, 3)),
        "face_score": float(risk.face_score if risk else 0.0),
        "pose_score": float(risk.pose_score if risk else 0.0),
        "object_score": float(risk.object_score if risk else 0.0),
        "audio_score": float(risk.audio_score if risk else 0.0),
        "browser_score": float(risk.browser_score if risk else 0.0),
    }

    # ── Integrity assessment (stored or compute now) ──────────────
    integrity_assessment = None
    try:
        raw = getattr(session, "integrity_assessment", None)
        if raw:
            integrity_assessment = json.loads(raw)
    except Exception:
        pass

    if integrity_assessment is None:
        try:
            from ai_engine.risk_engine.integrity_scorer import integrity_scorer

            vtype_map = {}
            for v in viol_list:
                vt = v["violation_type"]
                vtype_map[vt] = vtype_map.get(vt, 0) + 1
            assessment = integrity_scorer.assess(
                {
                    "session_id": session_id,
                    "duration_seconds": float(duration * 60),
                    "violations": viol_list,
                    "peak_risk_score": float(final_score),
                    "final_risk_score": float(final_score),
                    "face_verify_score": float(
                        getattr(session, "face_verify_score", None) or 1.0
                    ),
                    "gaze_summary": {},
                    "reverify_failures": int(vtype_map.get("FACE_MISMATCH", 0)),
                    "tab_switches": int(vtype_map.get("TAB_SWITCH", 0)),
                    "phone_detected_count": int(vtype_map.get("PHONE_DETECTED", 0)),
                    "speech_count": int(
                        vtype_map.get("SPEECH_BURST", 0)
                        + vtype_map.get("SUSTAINED_SPEECH", 0)
                    ),
                    "multi_speaker_count": int(vtype_map.get("MULTI_SPEAKER", 0)),
                    "was_terminated": (
                        session.status.value == "terminated"
                        if hasattr(session.status, "value")
                        else False
                    ),
                }
            )
            integrity_assessment = assessment.to_dict()
        except Exception as e:
            logger.error(f"On-the-fly integrity assessment failed: {e}")

    # ── Gaze summary ──────────────────────────────────────────────
    gaze_summary = None
    try:
        raw = getattr(session, "gaze_summary", None)
        if raw:
            gaze_summary = json.loads(raw)
    except Exception:
        pass

    # ── Score timeline (every 5th snapshot stored on session) ─────
    score_timeline = []
    try:
        raw = getattr(session, "score_timeline", None)
        if raw:
            score_timeline = json.loads(raw)
    except Exception:
        pass

    # Fallback: build rough timeline from violation timestamps
    if not score_timeline and viol_list:
        cum = 0.0
        for v in viol_list:
            cum += v["weight"]
            score_timeline.append(
                {
                    "timestamp": v["timestamp"],
                    "score": min(100.0, round(cum / 5.0, 1)),
                    "level": "WARNING" if cum / 5.0 > 30 else "SAFE",
                }
            )

    return {
        "session_id": session_id,
        "candidate": {
            "name": user.full_name if user else "Unknown",
            "email": user.email if user else "",
        },
        "exam": {
            "title": exam.title if exam else "Unknown",
            "started_at": started,
            "submitted_at": submitted,
            "duration_min": float(round(duration, 1)),
        },
        "risk_assessment": risk_assessment,
        "violations": viol_list,
        "module_stats": module_stats,
        "total_violations": len(viol_list),
        "gaze_summary": gaze_summary,
        "integrity_assessment": integrity_assessment,
        "score_timeline": score_timeline,
        "can_download": False,  # set per-role in endpoints
    }


# ── GET /reports/{session_id} ─────────────────────────────────────
@router.get("/{session_id}")
def get_report(
    session_id: str,
    token_data: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    role = token_data.get("role", "student")
    if role != "admin":
        user = db.query(User).filter(User.email == token_data["sub"]).first()
        if not user or session.user_id != user.id:
            raise HTTPException(403, "You can only view your own report.")

    data = _build_session_data(session_id, db)
    data["can_download"] = role == "admin"  # students always False
    return data


# ── POST /reports/generate/{session_id} ──────────────────────────
@router.post("/generate/{session_id}")
def generate_report(
    session_id: str,
    token_data: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    role = token_data.get("role", "student")
    if role != "admin":
        user = db.query(User).filter(User.email == token_data["sub"]).first()
        session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
        if not user or not session or session.user_id != user.id:
            raise HTTPException(403, "Not authorised.")
    try:
        from services.report_services import report_service

        data = _build_session_data(session_id, db)
        report_service.generate(data)
        return {"message": "Report generated", "session_id": session_id}
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(500, f"Report generation failed: {e}")


# ── GET /reports/{session_id}/download  (admin only) ─────────────
@router.get("/{session_id}/download")
def download_report(
    session_id: str,
    token_data: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")
    if not os.path.exists(pdf_path):
        try:
            from services.report_services import report_service

            data = _build_session_data(session_id, db)
            report_service.generate(data)
        except Exception as e:
            raise HTTPException(500, f"Could not generate report: {e}")
    if not os.path.exists(pdf_path):
        raise HTTPException(404, "Report file not found after generation.")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report_{session_id[:8]}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


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
# from fastapi.responses import FileResponse, Response
# from sqlalchemy.orm import Session

# from core.security import get_current_user_payload, require_role
# from db.session import get_db
# from db.models import ExamSession, Violation, RiskScore, User, Exam
# from services.report_services import report_service

# logger = logging.getLogger(__name__)
# router = APIRouter(prefix="/reports", tags=["Reports"])

# REPORTS_DIR = "storage/reports"


# def _build_session_data(session_id: str, db: Session) -> dict:
#     """Pull all data needed to generate a report from the DB."""

#     session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
#     if not session:
#         raise HTTPException(404, "Session not found")

#     user = db.query(User).filter(User.id == session.user_id).first()
#     exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
#     risk = db.query(RiskScore).filter(RiskScore.session_id == session_id).first()

#     violations = (
#         db.query(Violation)
#         .filter(Violation.session_id == session_id)
#         .order_by(Violation.timestamp)
#         .all()
#     )

#     # Serialize violations
#     viol_list = [
#         {
#             "timestamp": v.timestamp.timestamp() if v.timestamp else 0,
#             "violation_type": v.violation_type.value,
#             "source_module": _module_from_type(v.violation_type.value),
#             "confidence": v.confidence or 1.0,
#             "weight": v.weight,
#             "duration_secs": v.duration_secs or 0,
#             "description": v.description or "",
#             "screenshot": v.screenshot_path,
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
#                 "total_weight": 0.0,
#                 "type_counts": {},
#                 "anomaly_detected": False,
#             }
#         module_stats[mod]["violation_count"] += 1
#         module_stats[mod]["total_weight"] += v["weight"] * v["confidence"]
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

#     started = session.started_at.timestamp() if session.started_at else 0
#     submitted = session.submitted_at.timestamp() if session.submitted_at else 0

#     return {
#         "session_id": session_id,
#         "user_name": user.full_name if user else "Unknown",
#         "user_email": user.email if user else "Unknown",
#         "exam_title": exam.title if exam else "Unknown",
#         "started_at": started,
#         "submitted_at": submitted,
#         "final_score": risk.current_score if risk else 0.0,
#         "peak_score": risk.current_score if risk else 0.0,
#         "risk_level": risk.risk_level.value if risk else "SAFE",
#         "cheat_probability": 0.0,
#         "total_violations": len(viol_list),
#         "violations": viol_list,
#         "module_stats": module_stats,
#         "anomaly_flags": [],
#         "score_timeline": [],
#         "behavior_summary": {
#             "total_violations": len(viol_list),
#             "risk_contribution": sum(v["weight"] for v in viol_list),
#         },
#     }


# def _module_from_type(vtype: str) -> str:
#     mapping = {
#         "FACE_ABSENT": "face",
#         "FACE_MISMATCH": "face",
#         "MULTI_FACE": "face",
#         "LOOKING_AWAY": "pose",
#         "PHONE_DETECTED": "object",
#         "BOOK_DETECTED": "object",
#         "HEADPHONE_DETECTED": "object",
#         "SPEECH_BURST": "audio",
#         "SUSTAINED_SPEECH": "audio",
#         "MULTI_SPEAKER": "audio",
#         "WHISPER": "audio",
#         "TAB_SWITCH": "browser",
#         "WINDOW_BLUR": "browser",
#         "FULLSCREEN_EXIT": "browser",
#         "COPY_PASTE": "browser",
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
#     session_id: str,
#     token_data: dict = Depends(get_current_user_payload),
#     db: Session = Depends(get_db),
# ):
#     data = _build_session_data(session_id, db)
#     paths = report_service.generate(data)
#     return {
#         "message": "Report generated",
#         "pdf_path": paths["pdf"],
#         "json_path": paths["json"],
#         "session_id": session_id,
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
#     session_id: str,
#     token_data: dict = Depends(get_current_user_payload),
#     db: Session = Depends(get_db),
# ):
#     session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
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
#     session_id: str,
#     token_data: dict = Depends(require_role("admin")),  # ← admin only
#     db: Session = Depends(get_db),
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

#     with open(pdf_path, "rb") as f:
#         pdf_bytes = f.read()

#     return Response(
#         content=pdf_bytes,
#         media_type="application/pdf",
#         headers={
#             "Content-Disposition": f'attachment; filename="report_{session_id[:8]}.pdf"',
#         },
#     )
