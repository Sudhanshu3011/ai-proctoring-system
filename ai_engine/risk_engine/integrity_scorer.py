"""
Fixes:
  1. face_absent_count now derived from violations list (was missing)
  2. Cheat probability uses cumulative weighted-sum formula, not just
     sigmoid(deductions). Deductions can be misleading — 2 moderate
     violations don't equal 1 severe one. Fixed with per-violation
     weight accumulation.
  3. Confidence formula improved — also considers violation diversity
  4. All inputs properly typed; no AttributeError on missing fields
"""

import time
import math
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IntegrityFinding:
    category: str
    finding: str
    weight: float
    evidence: str


@dataclass
class IntegrityAssessment:
    integrity_score: float
    cheat_probability: float
    confidence: float
    verdict: str
    risk_band: str
    findings: list = field(default_factory=list)
    recommended_action: str = ""
    action_priority: str = ""
    session_id: str = ""
    exam_duration_min: float = 0.0
    total_violations: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "integrity_score": float(round(self.integrity_score, 1)),
            "cheat_probability": float(round(self.cheat_probability, 3)),
            "confidence": float(round(self.confidence, 2)),
            "verdict": str(self.verdict),
            "risk_band": str(self.risk_band),
            "findings": [
                {
                    "category": f.category,
                    "finding": f.finding,
                    "evidence": f.evidence,
                    "weight": float(round(f.weight, 1)),
                }
                for f in self.findings
            ],
            "recommended_action": str(self.recommended_action),
            "action_priority": str(self.action_priority),
            "total_violations": int(self.total_violations),
            "exam_duration_min": float(round(self.exam_duration_min, 1)),
        }


class IntegrityScorer:

    def assess(self, data: dict) -> IntegrityAssessment:
        findings = []
        deductions = 0.0

        duration_min = float(data.get("duration_seconds", 0)) / 60.0
        violations = data.get("violations", [])
        total_viols = len(violations)

        # ── Derive counts from violations list (fix: was using missing keys) ──
        vtype_map: dict[str, int] = {}
        total_weight = 0.0
        for v in violations:
            vt = (v.get("violation_type") or "").upper()
            vtype_map[vt] = vtype_map.get(vt, 0) + 1
            total_weight += float(v.get("weight", 0) or 0)

        face_absent_count = int(
            vtype_map.get("FACE_ABSENT", 0) + vtype_map.get("FACE_NOT_DETECTED", 0)
        )
        phone_count = int(vtype_map.get("PHONE_DETECTED", 0))
        tab_count = int(vtype_map.get("TAB_SWITCH", 0))
        speech_count = int(
            vtype_map.get("SPEECH_BURST", 0) + vtype_map.get("SUSTAINED_SPEECH", 0)
        )
        multi_speaker = int(vtype_map.get("MULTI_SPEAKER", 0))
        look_away = int(vtype_map.get("LOOKING_AWAY", 0))
        multi_face = int(vtype_map.get("MULTI_FACE", 0))
        # Override with explicit keys if provided (from _close_session)
        phone_count = int(data.get("phone_detected_count", phone_count))
        tab_count = int(data.get("tab_switches", tab_count))
        speech_count = int(data.get("speech_count", speech_count))
        multi_speaker = int(data.get("multi_speaker_count", multi_speaker))

        reverify_fails = int(data.get("reverify_failures", 0))
        verify_score = float(data.get("face_verify_score", 1.0) or 1.0)
        gaze = data.get("gaze_summary", {}) or {}
        peak = float(data.get("peak_risk_score", 0))
        was_terminated = bool(data.get("was_terminated", False))

        # ── 1: Identity ───────────────────────────────────────────
        if verify_score < 0.75:
            d = min(40.0, (0.75 - verify_score) * 120)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "IDENTITY",
                    f"Pre-exam identity verification low ({verify_score:.2f})",
                    d,
                    f"Required ≥0.75, got {verify_score:.3f}",
                )
            )

        if reverify_fails > 0:
            d = min(45.0, reverify_fails * 15.0)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "IDENTITY",
                    f"Mid-exam identity mismatch {reverify_fails}×",
                    d,
                    f"{reverify_fails} re-verification failure(s)",
                )
            )

        if multi_face > 0:
            d = min(25.0, multi_face * 12.0)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "IDENTITY",
                    f"Multiple faces detected in camera {multi_face}×",
                    d,
                    "Another person may have been present",
                )
            )

        # ── 2: Attention / gaze ───────────────────────────────────
        off_pct = float(gaze.get("off_screen_pct", 0))
        corner_pct = float(gaze.get("corner_pct", 0))

        if off_pct > 30:
            d = min(25.0, (off_pct - 30) * 0.85)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "ATTENTION",
                    f"Gaze off-screen {off_pct:.0f}% of exam",
                    d,
                    gaze.get("suspicion_note", "Possible second monitor"),
                )
            )
        elif off_pct > 15:
            deductions += 8.0
            findings.append(
                IntegrityFinding(
                    "ATTENTION",
                    f"Elevated off-screen gaze ({off_pct:.0f}%)",
                    8.0,
                    "Normal threshold is <15%",
                )
            )

        if corner_pct > 25:
            deductions += 12.0
            findings.append(
                IntegrityFinding(
                    "ATTENTION",
                    f"Frequent corner gaze ({corner_pct:.0f}%)",
                    12.0,
                    "May indicate checking notes/devices in periphery",
                )
            )

        if face_absent_count > 20:
            d = min(20.0, face_absent_count * 0.5)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "ATTENTION",
                    f"Face absent {face_absent_count}× during exam",
                    d,
                    "Camera view was empty repeatedly",
                )
            )

        if look_away > 10:
            d = min(15.0, (look_away - 10) * 0.8)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "ATTENTION",
                    f"Repeated head-pose violations ({look_away}×)",
                    d,
                    "Candidate looked away from screen repeatedly",
                )
            )

        # ── 3: Prohibited objects ─────────────────────────────────
        if phone_count > 0:
            d = min(40.0, phone_count * 10.0)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "OBJECTS",
                    f"Mobile phone detected {phone_count}×",
                    d,
                    "Detected by YOLOv8 object classifier",
                )
            )

        book_count = int(vtype_map.get("BOOK_DETECTED", 0))
        if book_count > 0:
            d = min(20.0, book_count * 8.0)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "OBJECTS",
                    f"Book/notes visible {book_count}×",
                    d,
                    "Reference material visible during exam",
                )
            )

        # ── 4: Audio ──────────────────────────────────────────────
        if multi_speaker > 0:
            d = min(30.0, multi_speaker * 12.0)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "AUDIO",
                    f"Multiple speakers detected {multi_speaker}×",
                    d,
                    "Another person may have been assisting",
                )
            )
        elif speech_count > 5:
            d = min(15.0, speech_count * 1.5)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "AUDIO",
                    f"Repeated speech events ({speech_count}×)",
                    d,
                    "Candidate may have been communicating",
                )
            )

        # ── 5: Browser behaviour ──────────────────────────────────
        if tab_count > 0:
            d = min(25.0, tab_count * 6.0)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "BROWSER",
                    f"Tab switched {tab_count}×",
                    d,
                    "Browser tab changed during exam",
                )
            )

        copy_paste = int(vtype_map.get("COPY_PASTE", 0))
        if copy_paste > 0:
            d = min(15.0, copy_paste * 7.0)
            deductions += d
            findings.append(
                IntegrityFinding(
                    "BROWSER",
                    f"Copy/paste detected {copy_paste}×",
                    d,
                    "Clipboard activity during exam",
                )
            )

        # ── 6: Exam termination ───────────────────────────────────
        if was_terminated:
            deductions += 30.0
            findings.append(
                IntegrityFinding(
                    "BEHAVIOUR",
                    "Exam auto-terminated — critical risk threshold",
                    30.0,
                    f"Peak score {peak:.1f}/100 triggered termination",
                )
            )

        # ── 7: Risk score pattern ─────────────────────────────────
        if peak >= 85:
            deductions += 20.0
            findings.append(
                IntegrityFinding(
                    "BEHAVIOUR",
                    f"Peak risk score critical ({peak:.1f})",
                    20.0,
                    "Systematic violations triggered critical risk",
                )
            )
        elif peak >= 60:
            deductions += 10.0
            findings.append(
                IntegrityFinding(
                    "BEHAVIOUR",
                    f"Peak risk score high ({peak:.1f})",
                    10.0,
                    "Multiple concurrent violations detected",
                )
            )

        # ── 8: Violation density ──────────────────────────────────
        if duration_min > 0:
            vpm = total_viols / duration_min
            if vpm > 3:
                d = min(15.0, (vpm - 3) * 2.5)
                deductions += d
                findings.append(
                    IntegrityFinding(
                        "BEHAVIOUR",
                        f"High violation density ({vpm:.1f}/min)",
                        d,
                        f"{total_viols} violations in {duration_min:.0f} minutes",
                    )
                )

        # ── Compute scores ────────────────────────────────────────
        deductions = min(deductions, 100.0)
        integrity_score = float(max(0.0, 100.0 - deductions))

        # Cumulative cheat probability:
        # Uses total_weight from all violations + deductions together.
        # This means P only grows as evidence accumulates — never resets.
        # Sigmoid inflection at combined_signal=40 (P=0.5).
        combined_signal = (
            total_weight / max(1.0, duration_min * 10.0)
        ) + deductions * 0.5
        k = 0.10
        cheat_probability = float(1.0 / (1.0 + math.exp(-k * (combined_signal - 40))))

        # Confidence: how sure are we about this assessment?
        # Higher with more violations, diversity of types, and long exam.
        type_diversity = len([k for k in vtype_map if vtype_map[k] > 0])
        confidence = float(
            min(
                1.0,
                0.30
                + min(0.40, total_viols * 0.02)
                + min(0.15, type_diversity * 0.03)
                + (0.10 if peak > 50 else 0.0)
                + (0.05 if duration_min > 30 else 0.0),
            )
        )

        # Verdict classification
        if cheat_probability < 0.25:
            verdict = "LIKELY_HONEST"
        elif cheat_probability < 0.55:
            verdict = "SUSPICIOUS"
        elif cheat_probability < 0.80:
            verdict = "LIKELY_CHEATING"
        else:
            verdict = "CONFIRMED_CHEATING"

        risk_band = next(
            b
            for t, b in [
                (0.25, "LOW"),
                (0.55, "MEDIUM"),
                (0.80, "HIGH"),
                (1.01, "VERY_HIGH"),
            ]
            if cheat_probability < t
        )

        actions = {
            "LIKELY_HONEST": ("No action required. Session appears normal.", "REVIEW"),
            "SUSPICIOUS": (
                "Manual review recommended. Examine violation timestamps.",
                "INVESTIGATE",
            ),
            "LIKELY_CHEATING": ("Withhold result pending investigation.", "ESCALATE"),
            "CONFIRMED_CHEATING": (
                "Invalidate result. Contact candidate for hearing.",
                "INVALIDATE",
            ),
        }
        recommended_action, action_priority = actions[verdict]

        findings.sort(key=lambda f: f.weight, reverse=True)

        logger.info(
            f"Integrity | session={data.get('session_id','?')[:8]} | "
            f"score={integrity_score:.1f} | "
            f"P(cheat)={cheat_probability:.2f} | verdict={verdict}"
        )

        return IntegrityAssessment(
            integrity_score=float(round(integrity_score, 1)),
            cheat_probability=float(round(cheat_probability, 3)),
            confidence=float(round(confidence, 2)),
            verdict=str(verdict),
            risk_band=str(risk_band),
            findings=findings,
            recommended_action=str(recommended_action),
            action_priority=str(action_priority),
            session_id=str(data.get("session_id", "")),
            exam_duration_min=float(round(duration_min, 1)),
            total_violations=int(total_viols),
        )


integrity_scorer = IntegrityScorer()
