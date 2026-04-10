"""
ai_engine/risk_engine/integrity_scorer.py

Exam Integrity Scorer — Final ML-based Assessment

Takes all session data (violations, risk scores, gaze data, timing)
and produces a comprehensive integrity assessment with:
  - Overall integrity score (0-100, higher = more trustworthy)
  - Cheating probability band (Low / Medium / High / Very High)
  - Evidence-based finding list
  - Recommended admin action
  - Confidence in the assessment

This runs ONCE at exam submission, not in real-time.
Think of it as the final verdict that the PDF report includes.
"""

import time
import math
import logging
from dataclasses import dataclass, field
from typing      import Optional

logger = logging.getLogger(__name__)


@dataclass
class IntegrityFinding:
    """One piece of evidence used in the integrity assessment."""
    category      : str    # IDENTITY | ATTENTION | OBJECTS | AUDIO | BROWSER | LIVENESS | BEHAVIOUR
    finding       : str    # human-readable finding
    weight        : float  # how much this affects the score
    evidence      : str    # specific data supporting the finding


@dataclass
class IntegrityAssessment:
    """
    Final integrity assessment for one exam session.
    Included in the PDF report and visible to admin.
    """
    # Scores
    integrity_score   : float   # 0–100 (100 = fully trustworthy)
    cheat_probability : float   # 0.0–1.0
    confidence        : float   # 0.0–1.0 (how confident we are in the assessment)

    # Classification
    verdict           : str     # LIKELY_HONEST | SUSPICIOUS | LIKELY_CHEATING | CONFIRMED_CHEATING
    risk_band         : str     # LOW | MEDIUM | HIGH | VERY_HIGH

    # Evidence
    findings          : list    = field(default_factory=list)

    # Recommendation
    recommended_action: str     = ""
    action_priority   : str     = ""   # REVIEW | INVESTIGATE | ESCALATE | INVALIDATE

    # Context
    session_id        : str     = ""
    exam_duration_min : float   = 0.0
    total_violations  : int     = 0
    timestamp         : float   = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "integrity_score"   : float(round(self.integrity_score,   1)),
            "cheat_probability" : float(round(self.cheat_probability, 3)),
            "confidence"        : float(round(self.confidence,        2)),
            "verdict"           : str(self.verdict),
            "risk_band"         : str(self.risk_band),
            "findings"          : [
                {
                    "category": f.category,
                    "finding" : f.finding,
                    "evidence": f.evidence,
                    "weight"  : float(round(f.weight, 1)),
                }
                for f in self.findings
            ],
            "recommended_action": str(self.recommended_action),
            "action_priority"   : str(self.action_priority),
            "total_violations"  : int(self.total_violations),
            "exam_duration_min" : float(round(self.exam_duration_min, 1)),
        }


class IntegrityScorer:
    """
    Produces a final integrity assessment from session data.

    Usage:
        scorer = IntegrityScorer()
        assessment = scorer.assess(session_data)

    session_data dict structure:
        session_id, duration_seconds, violations (list),
        peak_risk_score, final_risk_score, face_verify_score,
        gaze_summary (GazeSessionData.to_dict()),
        reverify_failures, tab_switches, face_absent_count,
        phone_detected_count, speech_count, was_terminated
    """

    def assess(self, data: dict) -> IntegrityAssessment:
        findings = []
        deductions = 0.0   # points deducted from 100

        duration_min  = float(data.get('duration_seconds', 0)) / 60.0
        violations    = data.get('violations', [])
        total_viols   = len(violations)

        # ── Evidence 1: Identity verification ────────────────────
        verify_score = float(data.get('face_verify_score', 1.0) or 1.0)
        reverify_fails = int(data.get('reverify_failures', 0))

        if verify_score < 0.75:
            d = min(40, (0.75 - verify_score) * 100)
            deductions += d
            findings.append(IntegrityFinding(
                category = "IDENTITY",
                finding  = f"Pre-exam identity verification low similarity ({verify_score:.2f})",
                weight   = d,
                evidence = f"Required: 0.75, Got: {verify_score:.3f}",
            ))

        if reverify_fails > 0:
            d = reverify_fails * 15
            deductions += min(d, 45)
            findings.append(IntegrityFinding(
                category = "IDENTITY",
                finding  = f"Mid-exam identity mismatch detected {reverify_fails} time(s)",
                weight   = float(min(d, 45)),
                evidence = f"{reverify_fails} re-verification failure(s) during exam",
            ))

        # ── Evidence 2: Attention / gaze ─────────────────────────
        gaze = data.get('gaze_summary', {})
        off_pct    = float(gaze.get('off_screen_pct', 0))
        corner_pct = float(gaze.get('corner_pct', 0))
        face_absent= int(data.get('face_absent_count', 0))

        if off_pct > 30:
            d = min(25, (off_pct - 30) * 0.8)
            deductions += d
            findings.append(IntegrityFinding(
                category = "ATTENTION",
                finding  = f"Gaze was off-screen {off_pct:.0f}% of the time",
                weight   = d,
                evidence = gaze.get('suspicion_note', ''),
            ))
        elif off_pct > 15:
            deductions += 8
            findings.append(IntegrityFinding(
                category = "ATTENTION",
                finding  = f"Elevated off-screen gaze ({off_pct:.0f}%)",
                weight   = 8.0,
                evidence = "Normal range is below 15%",
            ))

        if corner_pct > 25:
            deductions += 12
            findings.append(IntegrityFinding(
                category = "ATTENTION",
                finding  = f"Frequent gaze to screen corners ({corner_pct:.0f}%)",
                weight   = 12.0,
                evidence = "May indicate checking notes or secondary displays in peripheral vision",
            ))

        if face_absent > 20:
            d = min(20, face_absent * 0.5)
            deductions += d
            findings.append(IntegrityFinding(
                category = "ATTENTION",
                finding  = f"Face absent from camera {face_absent} times",
                weight   = d,
                evidence = "Camera view was empty repeatedly",
            ))

        # ── Evidence 3: Prohibited objects ───────────────────────
        phone_count = int(data.get('phone_detected_count', 0))
        if phone_count > 0:
            d = min(40, phone_count * 8)
            deductions += d
            findings.append(IntegrityFinding(
                category = "OBJECTS",
                finding  = f"Mobile phone detected {phone_count} time(s)",
                weight   = d,
                evidence = "Phone detected by YOLOv8 object detector",
            ))

        # ── Evidence 4: Audio ─────────────────────────────────────
        speech_count   = int(data.get('speech_count', 0))
        multispeak_count = int(data.get('multi_speaker_count', 0))

        if multispeak_count > 0:
            d = min(30, multispeak_count * 10)
            deductions += d
            findings.append(IntegrityFinding(
                category = "AUDIO",
                finding  = f"Multiple speakers detected {multispeak_count} time(s)",
                weight   = d,
                evidence = "Indicates another person may be assisting",
            ))
        elif speech_count > 5:
            d = min(15, speech_count * 1.5)
            deductions += d
            findings.append(IntegrityFinding(
                category = "AUDIO",
                finding  = f"Repeated speech detected ({speech_count} events)",
                weight   = d,
                evidence = "Candidate may be communicating with someone",
            ))

        # ── Evidence 5: Browser behaviour ────────────────────────
        tab_switches = int(data.get('tab_switches', 0))
        if tab_switches > 0:
            d = min(25, tab_switches * 5)
            deductions += d
            findings.append(IntegrityFinding(
                category = "BROWSER",
                finding  = f"Tab switched {tab_switches} time(s)",
                weight   = d,
                evidence = "Browser tab was switched during exam",
            ))

        # ── Evidence 6: Termination ───────────────────────────────
        if data.get('was_terminated'):
            deductions += 30
            findings.append(IntegrityFinding(
                category = "BEHAVIOUR",
                finding  = "Exam was auto-terminated due to critical risk score",
                weight   = 30.0,
                evidence = f"Risk score reached {data.get('peak_risk_score', 0):.1f}/100",
            ))

        # ── Evidence 7: Risk score pattern ───────────────────────
        peak = float(data.get('peak_risk_score', 0))
        if peak >= 85:
            deductions += 20
            findings.append(IntegrityFinding(
                category = "BEHAVIOUR",
                finding  = f"Peak risk score reached critical level ({peak:.1f})",
                weight   = 20.0,
                evidence = "Risk score pattern indicates systematic cheating attempt",
            ))
        elif peak >= 60:
            deductions += 10
            findings.append(IntegrityFinding(
                category = "BEHAVIOUR",
                finding  = f"Risk score reached high level ({peak:.1f})",
                weight   = 10.0,
                evidence = "Multiple simultaneous violations detected",
            ))

        # ── Violation density ─────────────────────────────────────
        if duration_min > 0:
            viols_per_min = total_viols / duration_min
            if viols_per_min > 3:
                d = min(15, (viols_per_min - 3) * 3)
                deductions += d
                findings.append(IntegrityFinding(
                    category = "BEHAVIOUR",
                    finding  = f"High violation density: {viols_per_min:.1f} violations/minute",
                    weight   = d,
                    evidence = f"{total_viols} violations over {duration_min:.0f} minutes",
                ))

        # ── Compute final scores ──────────────────────────────────
        deductions        = min(deductions, 100.0)
        integrity_score   = float(max(0.0, 100.0 - deductions))
        cheat_probability = float(1.0 / (1.0 + math.exp(-0.08 * (deductions - 40))))
        confidence        = float(min(1.0, 0.4 + total_viols * 0.03 + (1 if peak > 50 else 0) * 0.2))

        # Verdict
        if cheat_probability < 0.25:
            verdict = "LIKELY_HONEST"
        elif cheat_probability < 0.55:
            verdict = "SUSPICIOUS"
        elif cheat_probability < 0.80:
            verdict = "LIKELY_CHEATING"
        else:
            verdict = "CONFIRMED_CHEATING"

        bands = [(0.25,"LOW"),(0.55,"MEDIUM"),(0.80,"HIGH"),(1.01,"VERY_HIGH")]
        risk_band = next(b for t, b in bands if cheat_probability < t)

        # Recommendation
        actions = {
            "LIKELY_HONEST"    : ("No action required. Session appears normal.",             "REVIEW"),
            "SUSPICIOUS"       : ("Manual review recommended. Check violation timestamps.",  "INVESTIGATE"),
            "LIKELY_CHEATING"  : ("Exam result should be withheld pending investigation.",   "ESCALATE"),
            "CONFIRMED_CHEATING": ("Invalidate exam result. Contact candidate for hearing.", "INVALIDATE"),
        }
        recommended_action, action_priority = actions[verdict]

        # Sort findings by weight descending
        findings.sort(key=lambda f: f.weight, reverse=True)

        logger.info(
            f"Integrity assessment | "
            f"session={data.get('session_id','?')[:8]} | "
            f"score={integrity_score:.1f} | "
            f"verdict={verdict} | "
            f"P(cheat)={cheat_probability:.2f}"
        )

        return IntegrityAssessment(
            integrity_score    = float(round(integrity_score, 1)),
            cheat_probability  = float(round(cheat_probability, 3)),
            confidence         = float(round(confidence, 2)),
            verdict            = str(verdict),
            risk_band          = str(risk_band),
            findings           = findings,
            recommended_action = str(recommended_action),
            action_priority    = str(action_priority),
            session_id         = str(data.get('session_id', '')),
            exam_duration_min  = float(round(duration_min, 1)),
            total_violations   = int(total_viols),
        )


integrity_scorer = IntegrityScorer()