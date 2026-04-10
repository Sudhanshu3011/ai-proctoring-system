"""
services/alert_service.py

Real-time Alert Service

Sends notifications when exam risk crosses thresholds:
  - Email to admin when risk hits HIGH (score >= 60)
  - Email to admin when phone detected
  - Email to admin when session auto-terminated
  - In-app notification via WebSocket (already handled by admin_ws)

Configure in .env:
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your@gmail.com
  SMTP_PASSWORD=your_app_password
  ALERT_FROM=proctoring@yourinstitution.com
  ALERT_TO=admin@yourinstitution.com   # comma-separated for multiple
  ALERTS_ENABLED=true
"""

import logging
import smtplib
import time
from email.mime.text      import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses          import dataclass
from typing               import Optional

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AlertEvent:
    alert_type    : str    # RISK_HIGH | PHONE_DETECTED | SESSION_TERMINATED | EXAM_COMPLETED
    session_id    : str
    user_name     : str
    user_email    : str
    exam_title    : str
    risk_score    : float
    risk_level    : str
    detail        : str    # human-readable detail
    timestamp     : float


class AlertService:
    """
    Sends email alerts to administrators for critical exam events.

    Usage:
        alert_service.send_alert(AlertEvent(...))

    The service is non-blocking — if email fails the exam continues.
    Cooldowns prevent alert spam (same session, same type: max 1 per 5 min).
    """

    COOLDOWN_SEC = 300   # 5 minutes between same alerts

    def __init__(self):
        self._enabled   = getattr(settings, 'ALERTS_ENABLED', False)
        self._last_sent : dict[str, float] = {}   # key: f"{session_id}:{alert_type}"

        if self._enabled:
            logger.info("AlertService enabled — email alerts active")
        else:
            logger.info("AlertService disabled (set ALERTS_ENABLED=true to enable)")

    def send_alert(self, event: AlertEvent) -> bool:
        """Send alert. Returns True if sent, False if skipped or failed."""
        if not self._enabled:
            # Log it even if email disabled
            logger.warning(
                f"ALERT [{event.alert_type}] | "
                f"session={event.session_id[:8]} | "
                f"user={event.user_name} | "
                f"score={event.risk_score:.1f} | "
                f"{event.detail}"
            )
            return False

        # Cooldown check
        key    = f"{event.session_id}:{event.alert_type}"
        now    = time.time()
        last   = self._last_sent.get(key, 0.0)
        if now - last < self.COOLDOWN_SEC:
            logger.debug(f"Alert suppressed (cooldown): {key}")
            return False

        try:
            self._send_email(event)
            self._last_sent[key] = now
            logger.info(f"Alert sent: {event.alert_type} | {event.user_name}")
            return True
        except Exception as e:
            logger.error(f"Alert send failed: {e}")
            return False

    def _send_email(self, event: AlertEvent):
        smtp_host = getattr(settings, 'SMTP_HOST',     'smtp.gmail.com')
        smtp_port = getattr(settings, 'SMTP_PORT',     587)
        smtp_user = getattr(settings, 'SMTP_USER',     '')
        smtp_pass = getattr(settings, 'SMTP_PASSWORD', '')
        from_addr = getattr(settings, 'ALERT_FROM',    smtp_user)
        to_addrs  = getattr(settings, 'ALERT_TO',      smtp_user)

        if isinstance(to_addrs, str):
            to_list = [a.strip() for a in to_addrs.split(',') if a.strip()]
        else:
            to_list = to_addrs

        if not to_list:
            logger.warning("No ALERT_TO addresses configured")
            return

        subject, body = self._build_email(event)

        msg               = MIMEMultipart('alternative')
        msg['Subject']    = subject
        msg['From']       = from_addr
        msg['To']         = ', '.join(to_list)
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, to_list, msg.as_string())

    def _build_email(self, event: AlertEvent) -> tuple[str, str]:
        level_colors = {
            'SAFE'    : '#059669',
            'WARNING' : '#d97706',
            'HIGH'    : '#dc2626',
            'CRITICAL': '#991b1b',
        }
        alert_labels = {
            'RISK_HIGH'          : 'High Risk Alert',
            'PHONE_DETECTED'     : 'Prohibited Device Detected',
            'SESSION_TERMINATED' : 'Exam Session Terminated',
            'EXAM_COMPLETED'     : 'Exam Completed',
            'FACE_MISMATCH'      : 'Identity Mismatch Detected',
        }
        col    = level_colors.get(event.risk_level, '#374151')
        label  = alert_labels.get(event.alert_type, event.alert_type)
        ts     = time.strftime('%d %b %Y %H:%M:%S UTC', time.gmtime(event.timestamp))

        subject = f"[ProctorAI] {label} — {event.user_name} ({event.exam_title})"

        body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:system-ui,sans-serif;background:#f8fafc;padding:24px;margin:0">
  <div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;
              border-radius:10px;overflow:hidden">

    <!-- Header -->
    <div style="background:{col};padding:20px 24px">
      <div style="color:#fff;font-size:18px;font-weight:700">{label}</div>
      <div style="color:rgba(255,255,255,0.85);font-size:12px;margin-top:4px">
        ProctorAI — Automated Alert
      </div>
    </div>

    <!-- Body -->
    <div style="padding:24px">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr><td style="padding:6px 0;color:#6b7280;width:140px">Candidate</td>
            <td style="padding:6px 0;font-weight:600;color:#111">{event.user_name}</td></tr>
        <tr><td style="padding:6px 0;color:#6b7280">Email</td>
            <td style="padding:6px 0;color:#111">{event.user_email}</td></tr>
        <tr><td style="padding:6px 0;color:#6b7280">Exam</td>
            <td style="padding:6px 0;color:#111">{event.exam_title}</td></tr>
        <tr><td style="padding:6px 0;color:#6b7280">Risk Score</td>
            <td style="padding:6px 0;font-weight:700;color:{col}">
              {event.risk_score:.1f} / 100 ({event.risk_level})
            </td></tr>
        <tr><td style="padding:6px 0;color:#6b7280">Time</td>
            <td style="padding:6px 0;color:#111">{ts}</td></tr>
        <tr><td style="padding:6px 0;color:#6b7280">Session ID</td>
            <td style="padding:6px 0;color:#9ca3af;font-size:11px">{event.session_id}</td></tr>
      </table>

      <!-- Detail -->
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:3px solid {col};
                  border-radius:6px;padding:12px 14px;margin-top:16px;font-size:13px;color:#374151">
        {event.detail}
      </div>

      <!-- Action -->
      <div style="margin-top:20px;padding-top:16px;border-top:1px solid #e2e8f0;
                  font-size:12px;color:#6b7280">
        Log in to the ProctorAI admin dashboard to review this session and take action.
      </div>
    </div>
  </div>
</body>
</html>
"""
        return subject, body


# ── Singleton ─────────────────────────────────────────────────────
alert_service = AlertService()


# ── Helper called from monitoring/exam endpoints ──────────────────
def maybe_alert(
    session_id  : str,
    user_name   : str,
    user_email  : str,
    exam_title  : str,
    risk_score  : float,
    risk_level  : str,
    alert_type  : str,
    detail      : str,
):
    """Convenience wrapper — non-blocking alert dispatch."""
    import threading
    event = AlertEvent(
        alert_type  = alert_type,
        session_id  = session_id,
        user_name   = user_name,
        user_email  = user_email,
        exam_title  = exam_title,
        risk_score  = float(risk_score),
        risk_level  = str(risk_level),
        detail      = detail,
        timestamp   = time.time(),
    )
    # Run in background thread so it never blocks the request
    threading.Thread(
        target=alert_service.send_alert,
        args=(event,),
        daemon=True,
    ).start()