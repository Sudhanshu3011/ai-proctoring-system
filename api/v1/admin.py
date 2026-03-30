"""
api/v1/admin.py

Admin Live Monitoring Endpoints

  GET  /api/v1/admin/dashboard          → summary stats
  GET  /api/v1/admin/live-sessions      → all active exam sessions + risk
  GET  /api/v1/admin/session/{id}       → single session full detail
  POST /api/v1/admin/terminate/{id}     → force-terminate a session
  WS   /ws/admin/live                   → real-time push of all session risks

WebSocket pushes every 3 seconds:
    {
      "type": "SESSION_UPDATE",
      "sessions": [
        {
          "session_id":   "...",
          "user_name":    "Sudhanshu",
          "exam_title":   "Python Midterm",
          "risk_score":   72.4,
          "risk_level":   "HIGH",
          "violations":   14,
          "duration_min": 23,
          "face_score":   12.0,
          "pose_score":   34.0,
          "object_score": 0.0,
          "audio_score":  18.0,
          "browser_score":8.0
        }
      ],
      "summary": {
        "total_active": 3,
        "high_risk":    1,
        "critical":     0
      }
    }

Register in main.py:
    from api.v1.admin import router as admin_router, admin_ws_router
    app.include_router(admin_router,    prefix=API_PREFIX)
    app.include_router(admin_ws_router)
"""

import time
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.security import get_current_user_payload, require_role
from db.session    import get_db
from db.models     import (
    ExamSession, User, Exam, Violation, RiskScore,
    SessionStatus, RiskLevel,
)

logger         = logging.getLogger(__name__)
router         = APIRouter(prefix="/admin", tags=["Admin"])
admin_ws_router = APIRouter(tags=["Admin WebSocket"])

# ── Import active scorers from state ──────────────────────────────
try:
    from api.v1.state import _active_scorers
except ImportError:
    from api.v1.exam  import _active_scorers


# ─────────────────────────────────────────────
#  Helper — build live session dict
# ─────────────────────────────────────────────
def _build_live_session(session: ExamSession, db: Session) -> dict:
    """Pull full live state for one active session."""
    user  = db.query(User).filter(User.id == session.user_id).first()
    exam  = db.query(Exam).filter(Exam.id == session.exam_id).first()
    risk  = db.query(RiskScore).filter(
        RiskScore.session_id == session.id
    ).first()
    viol_count = db.query(Violation).filter(
        Violation.session_id == session.id
    ).count()

    # Duration in minutes
    started = session.started_at
    now_utc = datetime.now(timezone.utc)
    if started:
        if started.tzinfo is None:
            from datetime import timezone as tz
            started = started.replace(tzinfo=tz.utc)
        duration_min = int((now_utc - started).total_seconds() / 60)
    else:
        duration_min = 0

    # Get live score from in-memory scorer if available
    scorer = _active_scorers.get(session.id)
    live_score = scorer.current_score()    if scorer else (risk.current_score if risk else 0.0)
    live_level = scorer.current_level()   if scorer else (risk.risk_level.value if risk else "SAFE")
    live_prob  = scorer.current_probability() if scorer else 0.0

    return {
        "session_id"      : session.id,
        "user_id"         : session.user_id,
        "user_name"       : user.full_name if user else "Unknown",
        "user_email"      : user.email     if user else "Unknown",
        "exam_id"         : session.exam_id,
        "exam_title"      : exam.title     if exam else "Unknown",
        "status"          : session.status.value,
        "risk_score"      : round(live_score, 1),
        "risk_level"      : live_level,
        "cheat_probability": round(live_prob, 3),
        "violation_count" : viol_count,
        "duration_minutes": duration_min,
        "face_score"      : round(risk.face_score    if risk else 0.0, 1),
        "pose_score"      : round(risk.pose_score    if risk else 0.0, 1),
        "object_score"    : round(risk.object_score  if risk else 0.0, 1),
        "audio_score"     : round(risk.audio_score   if risk else 0.0, 1),
        "browser_score"   : round(risk.browser_score if risk else 0.0, 1),
        "started_at"      : session.started_at.isoformat() if session.started_at else None,
    }


def _build_summary(sessions_data: list) -> dict:
    levels = [s["risk_level"] for s in sessions_data]
    return {
        "total_active": len(sessions_data),
        "safe"        : levels.count("SAFE"),
        "warning"     : levels.count("WARNING"),
        "high_risk"   : levels.count("HIGH"),
        "critical"    : levels.count("CRITICAL"),
    }


# ─────────────────────────────────────────────
#  GET /admin/dashboard
# ─────────────────────────────────────────────
@router.get("/dashboard", summary="Admin dashboard summary stats")
def dashboard(
    token_data : dict    = Depends(require_role("admin")),
    db         : Session = Depends(get_db),
):
    active_sessions = db.query(ExamSession).filter(
        ExamSession.status == SessionStatus.ACTIVE
    ).all()

    sessions_data = [_build_live_session(s, db) for s in active_sessions]

    total_users  = db.query(User).count()
    total_exams  = db.query(Exam).count()
    total_viols  = db.query(Violation).count()

    return {
        "live_summary"   : _build_summary(sessions_data),
        "total_users"    : total_users,
        "total_exams"    : total_exams,
        "total_violations": total_viols,
        "active_sessions": sessions_data,
    }


# ─────────────────────────────────────────────
#  GET /admin/live-sessions
# ─────────────────────────────────────────────
@router.get("/live-sessions", summary="All active exam sessions with live risk")
def live_sessions(
    token_data : dict    = Depends(require_role("admin")),
    db         : Session = Depends(get_db),
):
    sessions = db.query(ExamSession).filter(
        ExamSession.status == SessionStatus.ACTIVE
    ).all()

    sessions_data = [_build_live_session(s, db) for s in sessions]

    return {
        "sessions": sessions_data,
        "summary" : _build_summary(sessions_data),
    }


# ─────────────────────────────────────────────
#  GET /admin/session/{session_id}
# ─────────────────────────────────────────────
@router.get("/session/{session_id}", summary="Full detail for one session")
def session_detail(
    session_id : str,
    token_data : dict    = Depends(require_role("admin")),
    db         : Session = Depends(get_db),
):
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    base = _build_live_session(session, db)

    # Last 20 violations
    violations = db.query(Violation).filter(
        Violation.session_id == session_id
    ).order_by(Violation.timestamp.desc()).limit(20).all()

    base["recent_violations"] = [
        {
            "type"      : v.violation_type.value,
            "weight"    : v.weight,
            "confidence": round(v.confidence or 0, 2),
            "timestamp" : v.timestamp.isoformat() if v.timestamp else None,
            "duration"  : v.duration_secs,
        }
        for v in violations
    ]
    return base


# ─────────────────────────────────────────────
#  POST /admin/terminate/{session_id}
# ─────────────────────────────────────────────
@router.post("/terminate/{session_id}", summary="Force-terminate a live session")
def admin_terminate(
    session_id : str,
    token_data : dict    = Depends(require_role("admin")),
    db         : Session = Depends(get_db),
):
    session = db.query(ExamSession).filter(
        ExamSession.id      == session_id,
        ExamSession.status  == SessionStatus.ACTIVE,
    ).first()
    if not session:
        raise HTTPException(404, "Active session not found")

    from api.v1.exam import _close_session
    result = _close_session(session, "TERMINATED", db)

    logger.warning(
        f"Admin terminated session | "
        f"session={session_id} | admin={token_data.get('sub')}"
    )
    return {"message": "Session terminated by admin", **result.model_dump()}


# ─────────────────────────────────────────────
#  WebSocket  /ws/admin/live
#  Pushes all live session data every 3 seconds
# ─────────────────────────────────────────────
@admin_ws_router.websocket("/ws/admin/live")
async def admin_live_ws(websocket: WebSocket):
    """
    Admin live monitoring WebSocket.
    No auth token sent via WS headers — token passed as query param:
        ws://localhost:8000/ws/admin/live?token=JWT_HERE

    Pushes SESSION_UPDATE every 3 seconds with all active sessions.
    Admin can send: {"type": "TERMINATE", "session_id": "..."}
    """
    token = websocket.query_params.get("token", "")

    # Validate token
    try:
        from core.security import decode_access_token
        payload = decode_access_token(token)
        if payload.get("role") != "admin":
            await websocket.close(code=4003, reason="Admin role required")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    logger.info(f"Admin WS connected | admin={payload.get('sub')}")

    from db.session import SessionLocal

    try:
        while True:
            # Build fresh data from DB
            db = SessionLocal()
            try:
                sessions = db.query(ExamSession).filter(
                    ExamSession.status == SessionStatus.ACTIVE
                ).all()
                sessions_data = [_build_live_session(s, db) for s in sessions]
            finally:
                db.close()

            # Push update
            await websocket.send_json({
                "type"    : "SESSION_UPDATE",
                "sessions": sessions_data,
                "summary" : _build_summary(sessions_data),
                "ts"      : time.time(),
            })

            # Listen for admin commands (non-blocking, 3s timeout)
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=3.0
                )
                if msg.get("type") == "TERMINATE":
                    sid = msg.get("session_id")
                    if sid:
                        db2 = SessionLocal()
                        try:
                            s = db2.query(ExamSession).filter(
                                ExamSession.id     == sid,
                                ExamSession.status == SessionStatus.ACTIVE,
                            ).first()
                            if s:
                                from api.v1.exam import _close_session
                                _close_session(s, "TERMINATED", db2)
                                await websocket.send_json({
                                    "type"      : "TERMINATED",
                                    "session_id": sid,
                                    "message"   : "Session terminated by admin",
                                })
                                logger.warning(
                                    f"Admin WS terminated session={sid}"
                                )
                        finally:
                            db2.close()

            except asyncio.TimeoutError:
                pass   # No command received — just push next update

    except WebSocketDisconnect:
        logger.info(f"Admin WS disconnected | admin={payload.get('sub')}")
    except Exception as e:
        logger.error(f"Admin WS error: {e}", exc_info=True)