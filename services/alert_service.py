"""
services/alert_service.py — EMAIL REMOVED

All SMTP / email sending has been removed.
Alerts are now:
  1. Logged to the application logger (always)
  2. Stored in-memory for admin WebSocket push (handled by admin.py)

The maybe_alert() function signature is unchanged so exam.py / monitoring.py
need zero changes. Only the internals are stripped.
"""

import logging
import time
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AlertEvent:
    alert_type: str  # RISK_HIGH | PHONE_DETECTED | SESSION_TERMINATED | EXAM_COMPLETED
    session_id: str
    user_name: str
    user_email: str
    exam_title: str
    risk_score: float
    risk_level: str
    detail: str
    timestamp: float


# In-memory alert log — visible to admin WebSocket endpoint
# Keyed by session_id, list of AlertEvent dicts (newest first)
_alert_log: dict[str, list[dict]] = {}
_log_lock = threading.Lock()
MAX_PER_SESSION = 50


class AlertService:
    """
    System-only alert service.  No email.  No SMTP.

    Alerts are:
      • Written to the Python logger (visible in server logs)
      • Stored in _alert_log for the admin live dashboard
    """

    COOLDOWN_SEC = 300  # 5 minutes between same alert type per session

    def __init__(self):
        self._last_sent: dict[str, float] = {}
        logger.info("AlertService initialised (email disabled — system-only mode)")

    def send_alert(self, event: AlertEvent) -> bool:
        # Cooldown check — prevent spam for the same session+type
        key = f"{event.session_id}:{event.alert_type}"
        now = time.time()
        last = self._last_sent.get(key, 0.0)
        if now - last < self.COOLDOWN_SEC:
            return False

        self._last_sent[key] = now

        # Log to server logger
        logger.warning(
            f"ALERT [{event.alert_type}] | "
            f"session={event.session_id[:8]} | "
            f"user={event.user_name} | "
            f"score={event.risk_score:.1f} | "
            f"{event.detail}"
        )

        # Store in in-memory log for admin dashboard
        entry = {
            "alert_type": event.alert_type,
            "session_id": event.session_id,
            "user_name": event.user_name,
            "exam_title": event.exam_title,
            "risk_score": float(event.risk_score),
            "risk_level": event.risk_level,
            "detail": event.detail,
            "timestamp": float(event.timestamp),
        }
        with _log_lock:
            sid = event.session_id
            if sid not in _alert_log:
                _alert_log[sid] = []
            _alert_log[sid].insert(0, entry)
            if len(_alert_log[sid]) > MAX_PER_SESSION:
                _alert_log[sid] = _alert_log[sid][:MAX_PER_SESSION]

        return True

    def get_session_alerts(self, session_id: str) -> list:
        with _log_lock:
            return list(_alert_log.get(session_id, []))

    def get_all_recent(self, limit: int = 100) -> list:
        """Return most recent alerts across all sessions (for admin dashboard)."""
        all_alerts = []
        with _log_lock:
            for events in _alert_log.values():
                all_alerts.extend(events)
        all_alerts.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_alerts[:limit]


# Singleton
alert_service = AlertService()


def maybe_alert(
    session_id: str,
    user_name: str,
    user_email: str,
    exam_title: str,
    risk_score: float,
    risk_level: str,
    alert_type: str,
    detail: str,
):
    """Non-blocking alert dispatch. Unchanged signature."""
    event = AlertEvent(
        alert_type=alert_type,
        session_id=session_id,
        user_name=user_name,
        user_email=user_email,
        exam_title=exam_title,
        risk_score=float(risk_score),
        risk_level=str(risk_level),
        detail=detail,
        timestamp=time.time(),
    )
    threading.Thread(
        target=alert_service.send_alert, args=(event,), daemon=True
    ).start()
