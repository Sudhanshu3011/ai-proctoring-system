"""
ai_engine/risk_engine/scoring.py

Risk Scoring Engine — AI Proctoring System

Converts raw violation events + behavior reports into a single
normalised 0–100 risk score with a cheating probability.

Formula (from project architecture):
    R = Σ(Wi · Fi · Ci · Di)

Where:
    Wi = violation weight (severity importance)
    Fi = frequency count
    Ci = AI confidence score (0–1)
    Di = duration factor = 1 + (Ti / T_threshold)

Then:
    R_normalized = (R / R_max) × 100          → 0–100 scale
    R_dynamic    = α·R_prev + (1-α)·R_current → sliding window
    P(cheat)     = 1 / (1 + e^(-k(R - θ)))   → sigmoid probability

Risk levels:
    0–30   → SAFE      (continue exam)
    30–60  → WARNING   (show popup to candidate)
    60–85  → HIGH      (alert admin)
    85–100 → CRITICAL  (auto-terminate exam)

Connects to:
    behavior_module/anomaly_detector.py → BehaviorReport input
    api/v1/monitoring.py                → called each frame
    workers/video_worker.py             → called each tick
    services/alert_service.py          → triggered on level change
    db/models.py                        → RiskScore table updates
"""

import time
import math
import logging
from dataclasses import dataclass, field
from typing import Optional

from ai_engine.logger import get_logger
from ai_engine.behaviour_module.anomaly_detector import (
    BehaviorReport,
    ViolationEvent,
    VIOLATION_WEIGHTS,
)

logger = get_logger("risk_engine")


# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
class RiskConfig:
    """All scoring parameters in one place."""

    # ── Per-violation weights ─────────────────────────────────────
    # Mirrors VIOLATION_WEIGHTS but can be overridden per exam
    WEIGHTS: dict[str, int] = VIOLATION_WEIGHTS

    # ── Duration factor ───────────────────────────────────────────
    # Di = 1 + (Ti / T_threshold)
    # Safe duration per type (seconds) — violation lasting longer
    # than this multiplies its contribution
    DURATION_THRESHOLDS: dict[str, float] = {
        "FACE_ABSENT"      : 3.0,
        "LOOKING_AWAY"     : 2.0,
        "SUSTAINED_SPEECH" : 3.0,
        "PHONE_DETECTED"   : 1.0,
        "BOOK_DETECTED"    : 2.0,
    }
    DEFAULT_DURATION_THRESHOLD = 5.0

    # ── Normalisation ─────────────────────────────────────────────
    # Theoretical max raw score — used to normalise to 0–100.
    # Set high enough that realistic exams don't peg at 100 instantly.
    R_MAX = 500.0

    # ── Sliding window (exponential moving average) ───────────────
    # R_t = α·R_(t-1) + (1-α)·ΔR_current
    # Higher α = more memory (slow to rise AND fall)
    # Lower  α = more reactive (quick to rise AND fall)
    ALPHA = 0.80

    # ── Sigmoid cheating probability ──────────────────────────────
    # P = 1 / (1 + e^(-k(R - θ)))
    # k = sensitivity (steeper curve = more decisive)
    # θ = inflection point (score at which P = 0.5)
    SIGMOID_K     = 0.12
    SIGMOID_THETA = 55.0    # score at which P(cheat) = 50%

    # ── Risk level thresholds ─────────────────────────────────────
    SAFE_MAX     = 30
    WARNING_MAX  = 60
    HIGH_MAX     = 85
    # above 85 → CRITICAL

    # ── Auto-termination ──────────────────────────────────────────
    TERMINATE_SCORE       = 85    # score at which exam is force-ended
    TERMINATE_PROBABILITY = 0.90  # OR if cheat probability > 90%

    # ── Per-module score caps ─────────────────────────────────────
    # Prevents one noisy module from dominating the total score
    MODULE_SCORE_CAPS: dict[str, float] = {
        "face"    : 150.0,
        "pose"    : 100.0,
        "object"  : 200.0,
        "audio"   : 100.0,
        "browser" : 80.0,
    }


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────
class RiskLevel:
    SAFE     = "SAFE"
    WARNING  = "WARNING"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ViolationScore:
    """Score contribution from a single violation event."""
    violation_type : str
    weight         : int
    frequency      : int
    confidence     : float
    duration_factor: float
    raw_score      : float    # Wi × Fi × Ci × Di
    source_module  : str


@dataclass
class RiskSnapshot:
    """
    Complete risk state at one point in time.
    Stored in DB (RiskScore table) and sent to frontend via WebSocket.
    """
    # Scores
    current_score      : float    # normalised 0–100, sliding window
    raw_score          : float    # R before normalisation
    cheat_probability  : float    # sigmoid output 0.0–1.0
    risk_level         : str      # SAFE | WARNING | HIGH | CRITICAL

    # Per-module breakdown
    face_score         : float = 0.0
    pose_score         : float = 0.0
    object_score       : float = 0.0
    audio_score        : float = 0.0
    browser_score      : float = 0.0

    # Flags
    should_warn        : bool  = False   # show popup to candidate
    should_alert_admin : bool  = False   # ping admin dashboard
    should_terminate   : bool  = False   # end exam immediately

    # Context
    timestamp          : float = field(default_factory=time.time)
    session_id         : str   = ""
    violation_count    : int   = 0
    anomaly_multiplier : float = 1.0

    

    def to_dict(self) -> dict:
        """All values cast to Python native types — safe for json.dumps and PostgreSQL."""
        return {
            "current_score"     : float(self.current_score),
            "raw_score"         : float(self.raw_score),
            "cheat_probability" : float(self.cheat_probability),
            "risk_level"        : str(self.risk_level),
            "face_score"        : float(self.face_score),
            "pose_score"        : float(self.pose_score),
            "object_score"      : float(self.object_score),
            "audio_score"       : float(self.audio_score),
            "browser_score"     : float(self.browser_score),
            "should_warn"       : bool(self.should_warn),       # ← fixes np.bool_
            "should_alert_admin": bool(self.should_alert_admin),
            "should_terminate"  : bool(self.should_terminate),
            "timestamp"         : float(self.timestamp),
            "session_id"        : str(self.session_id),
            "violation_count"   : int(self.violation_count),
            "anomaly_multiplier": float(self.anomaly_multiplier),
        }
    


# ─────────────────────────────────────────────
#  RiskScorer
# ─────────────────────────────────────────────
class RiskScorer:
    """
    Central risk scoring engine.

    Usage in proctoring pipeline:

        scorer = RiskScorer(session_id="sess_abc")

        # Each monitoring tick:
        report   = anomaly_detector.analyze()
        snapshot = scorer.update(report)

        # Check termination:
        if snapshot.should_terminate:
            exam_service.terminate(session_id)

        # Send to frontend via WebSocket:
        websocket.send(snapshot.to_dict())

        # End of exam:
        summary = scorer.get_session_summary()
    """

    def __init__(
        self,
        session_id : str = "",
        config     : RiskConfig = None,
    ):
        self.session_id = session_id
        self.config     = config or RiskConfig()

        # Sliding window state
        self._dynamic_score : float = 0.0   # R_t (exponential moving average)

        # Session history for report
        self._snapshots        : list[RiskSnapshot] = []
        self._all_events       : list[ViolationEvent] = []
        self._peak_score       : float = 0.0
        self._risk_level_times : dict[str, float] = {
            RiskLevel.SAFE    : 0.0,
            RiskLevel.WARNING : 0.0,
            RiskLevel.HIGH    : 0.0,
            RiskLevel.CRITICAL: 0.0,
        }
        self._prev_risk_level  : str   = RiskLevel.SAFE
        self._level_entry_time : float = time.time()

        logger.info(
            f"RiskScorer ready | "
            f"session={session_id} | "
            f"R_max={self.config.R_MAX} | "
            f"alpha={self.config.ALPHA}"
        )

    # ─────────────────────────────────────────
    #  Core formula components
    # ─────────────────────────────────────────
    def _duration_factor(self, event: ViolationEvent) -> float:
        """
        Di = 1 + (Ti / T_threshold)

        A violation that lasts twice the safe threshold has Di = 3.0,
        tripling its contribution vs a momentary detection.
        """
        if event.duration_secs <= 0:
            return 1.0
        threshold = self.config.DURATION_THRESHOLDS.get(
            event.violation_type,
            self.config.DEFAULT_DURATION_THRESHOLD,
        )
        return 1.0 + (event.duration_secs / threshold)

    def _compute_violation_score(
        self,
        event     : ViolationEvent,
        frequency : int,
    ) -> ViolationScore:
        """
        Single violation score:
            raw = Wi × Fi × Ci × Di
        """
        wi = self.config.WEIGHTS.get(event.violation_type, 10)
        fi = frequency
        ci = max(0.0, min(1.0, event.confidence))
        di = self._duration_factor(event)

        raw = wi * fi * ci * di

        return ViolationScore(
            violation_type  = event.violation_type,
            weight          = wi,
            frequency       = fi,
            confidence      = ci,
            duration_factor = round(di, 3),
            raw_score       = round(raw, 3),
            source_module   = event.source_module,
        )

    def _normalise(self, raw: float) -> float:
        """R_normalized = (R / R_max) × 100  →  clipped to 0–100."""
        return min(100.0, max(0.0, (raw / self.config.R_MAX) * 100.0))

    def _sliding_window(self, new_normalised: float) -> float:
        """
        Exponential moving average:
            R_t = α·R_(t-1) + (1-α)·R_current

        Prevents one bad moment from permanently destroying the score,
        and prevents score from growing to infinity on long exams.
        """
        self._dynamic_score = (
            self.config.ALPHA * self._dynamic_score
            + (1 - self.config.ALPHA) * new_normalised
        )
        return self._dynamic_score

    def _sigmoid_probability(self, score: float) -> float:
        """
        P(cheating) = 1 / (1 + e^(-k(R - θ)))

        Converts normalised score to a clean 0–1 cheating probability.
        At score=θ (55), P = 0.50.
        At score=85,     P ≈ 0.95.
        At score=30,     P ≈ 0.08.
        """
        k     = self.config.SIGMOID_K
        theta = self.config.SIGMOID_THETA
        try:
            return 1.0 / (1.0 + math.exp(-k * (score - theta)))
        except OverflowError:
            return 0.0 if score < theta else 1.0

    def _classify_level(self, score: float) -> str:
        if score <= self.config.SAFE_MAX:
            return RiskLevel.SAFE
        if score <= self.config.WARNING_MAX:
            return RiskLevel.WARNING
        if score <= self.config.HIGH_MAX:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    # ─────────────────────────────────────────
    #  Per-module score breakdown
    # ─────────────────────────────────────────
    def _module_scores(
        self,
        events     : list[ViolationEvent],
        freq_map   : dict[str, int],
    ) -> dict[str, float]:
        """
        Compute and cap per-module raw score contributions.
        Prevents one noisy module from dominating the total.
        """
        module_raw: dict[str, float] = {}

        for event in events:
            freq  = freq_map.get(event.violation_type, 1)
            vscore = self._compute_violation_score(event, freq)
            mod   = event.source_module or "unknown"
            module_raw[mod] = module_raw.get(mod, 0.0) + vscore.raw_score

        # Apply per-module caps
        module_capped: dict[str, float] = {}
        for mod, raw in module_raw.items():
            cap    = self.config.MODULE_SCORE_CAPS.get(mod, 200.0)
            capped = min(raw, cap)
            module_capped[mod] = round(capped, 2)

        return module_capped

    # ─────────────────────────────────────────
    #  Main update — call each monitoring tick
    # ─────────────────────────────────────────
    def update(self, report: BehaviorReport) -> RiskSnapshot:
        """
        Process a BehaviorReport and return an updated RiskSnapshot.

        Called by:
            workers/video_worker.py  every ~1s
            api/v1/monitoring.py     on each frame POST

        Steps:
            1. Extract events from report
            2. Compute R = Σ(Wi × Fi × Ci × Di) per module
            3. Apply anomaly multiplier from behavior module
            4. Normalise to 0–100
            5. Apply sliding window smoothing
            6. Compute sigmoid cheating probability
            7. Classify risk level
            8. Set action flags (warn / alert / terminate)
        """
        now    = time.time()
        events = [
            e for module_events in []  # placeholder — see below
            for e in module_events
        ]

        # Extract events from report's module stats
        # In practice, the caller passes events alongside the report.
        # Here we reconstruct frequency map from module_stats.
        freq_map: dict[str, int] = {}
        raw_total = 0.0

        # Use report's pre-computed adjusted score as our raw input
        # (anomaly_detector already applied W×F×C×D and multiplier)
        raw_total = report.adjusted_behavior_score

        # Per-module breakdown from report
        module_scores: dict[str, float] = {}
        for mod, stats in report.module_stats.items():
            cap    = self.config.MODULE_SCORE_CAPS.get(mod, 200.0)
            module_scores[mod] = min(stats.total_weight, cap)

        # ── Step 3: Apply anomaly multiplier ─────────────────────
        raw_adjusted = raw_total  # already includes multiplier from report

        # ── Step 4: Normalise ─────────────────────────────────────
        normalised = self._normalise(raw_adjusted)

        # ── Step 5: Sliding window ────────────────────────────────
        dynamic = self._sliding_window(normalised)

        # ── Step 6: Sigmoid probability ───────────────────────────
        cheat_prob = self._sigmoid_probability(dynamic)

        # ── Step 7: Classify ──────────────────────────────────────
        level = self._classify_level(dynamic)

        # Track time spent at each risk level
        if level != self._prev_risk_level:
            elapsed = now - self._level_entry_time
            self._risk_level_times[self._prev_risk_level] += elapsed
            self._prev_risk_level  = level
            self._level_entry_time = now
            logger.info(
                f"Risk level change → {level} | "
                f"score={dynamic:.1f} | P={cheat_prob:.3f}"
            )

        # Update peak
        if dynamic > self._peak_score:
            self._peak_score = dynamic

        # ── Step 8: Action flags ──────────────────────────────────
        should_warn      = dynamic > self.config.SAFE_MAX
        should_alert     = dynamic > self.config.WARNING_MAX
        should_terminate = (
            dynamic       >= self.config.TERMINATE_SCORE or
            cheat_prob    >= self.config.TERMINATE_PROBABILITY
        )

        snapshot = RiskSnapshot(
            current_score      = round(dynamic, 2),
            raw_score          = round(raw_adjusted, 2),
            cheat_probability  = round(cheat_prob, 4),
            risk_level         = level,
            face_score         = module_scores.get("face",    0.0),
            pose_score         = module_scores.get("pose",    0.0),
            object_score       = module_scores.get("object",  0.0),
            audio_score        = module_scores.get("audio",   0.0),
            browser_score      = module_scores.get("browser", 0.0),
            should_warn        = should_warn,
            should_alert_admin = should_alert,
            should_terminate   = should_terminate,
            timestamp          = now,
            session_id         = self.session_id,
            violation_count    = report.session_total_violations,
            anomaly_multiplier = report.anomaly_multiplier,
        )

        self._snapshots.append(snapshot)

        if should_terminate:
            logger.critical(
                f"TERMINATE TRIGGERED | "
                f"score={dynamic:.1f} P={cheat_prob:.3f} | "
                f"session={self.session_id}"
            )
        elif should_alert:
            logger.warning(
                f"HIGH RISK | score={dynamic:.1f} P={cheat_prob:.3f}"
            )

        return snapshot

    # ─────────────────────────────────────────
    #  Direct violation update (bypass anomaly detector)
    # ─────────────────────────────────────────
    def add_violation_direct(
        self,
        violation_type : str,
        confidence     : float = 1.0,
        duration_secs  : float = 0.0,
        source_module  : str   = "",
    ) -> float:
        """
        Add a single violation directly and return updated score.
        Useful for browser events (tab switch, copy-paste) that
        don't go through the AI pipeline.

        Returns: updated dynamic score (0–100)
        """
        weight  = self.config.WEIGHTS.get(violation_type, 10)
        t_thresh = self.config.DURATION_THRESHOLDS.get(
            violation_type, self.config.DEFAULT_DURATION_THRESHOLD
        )
        di      = 1.0 + (duration_secs / t_thresh) if duration_secs > 0 else 1.0
        raw     = weight * 1 * confidence * di
        norm    = self._normalise(raw)
        dynamic = self._sliding_window(norm)

        logger.warning(
            f"Direct violation | {violation_type} | "
            f"w={weight} conf={confidence:.2f} di={di:.2f} | "
            f"raw={raw:.1f} → score={dynamic:.1f}"
        )
        return round(dynamic, 2)

    # ─────────────────────────────────────────
    #  Score inspection
    # ─────────────────────────────────────────
    def current_score(self) -> float:
        return float(round(self._dynamic_score, 2))
    
    def current_level(self) -> str:
        return str(self._classify_level(self._dynamic_score))
    
    def current_probability(self) -> float:
        return float(round(self._sigmoid_probability(self._dynamic_score), 4))

    # ─────────────────────────────────────────
    #  Session summary (for report_service.py)
    # ─────────────────────────────────────────
    def get_session_summary(self) -> dict:
        """
        Full session risk summary for report_service.py.
        Includes score timeline, level durations, peak.
        """
        # Close out current level timer
        now     = time.time()
        elapsed = now - self._level_entry_time
        level_times = dict(self._risk_level_times)
        level_times[self._prev_risk_level] += elapsed

        return {
            "session_id"      : self.session_id,
            "final_score"     : self.current_score(),
            "peak_score"      : round(self._peak_score, 2),
            "final_level"     : self.current_level(),
            "cheat_probability": self.current_probability(),
            "total_snapshots" : len(self._snapshots),
            "time_at_levels"  : {
                k: round(v, 1) for k, v in level_times.items()
            },
            "score_timeline"  : [
                {
                    "timestamp"  : s.timestamp,
                    "score"      : s.current_score,
                    "level"      : s.risk_level,
                    "probability": s.cheat_probability,
                }
                for s in self._snapshots[::5]  # every 5th for size
            ],
        }

    def reset(self):
        """Clear state for a new session."""
        self._dynamic_score    = 0.0
        self._snapshots.clear()
        self._all_events.clear()
        self._peak_score       = 0.0
        self._prev_risk_level  = RiskLevel.SAFE
        self._level_entry_time = time.time()
        self._risk_level_times = {k: 0.0 for k in self._risk_level_times}
        logger.info(f"RiskScorer reset | session={self.session_id}")


# ─────────────────────────────────────────────
#  Standalone test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    from ai_engine.behaviour_module.anomaly_detector import (
        AnomalyDetector, ViolationEvent
    )

    print("\n── RiskScorer standalone test ───────────────────────────")

    det    = AnomalyDetector()
    scorer = RiskScorer(session_id="test_session")
    now    = time.time()

    # Simulate escalating exam violations
    phases = [
        # Phase 1 — quiet start
        [
            ViolationEvent("LOOKING_AWAY", now-110, 15, 0.90, 2.0, "pose"),
            ViolationEvent("LOOKING_AWAY", now-100, 15, 0.88, 1.8, "pose"),
        ],
        # Phase 2 — getting suspicious
        [
            ViolationEvent("TAB_SWITCH",      now-80, 20, 1.00, 0.0, "browser"),
            ViolationEvent("SPEECH_BURST",    now-70, 10, 0.75, 1.5, "audio"),
            ViolationEvent("LOOKING_AWAY",    now-60, 15, 0.91, 3.0, "pose"),
            ViolationEvent("LOOKING_AWAY",    now-50, 15, 0.94, 2.5, "pose"),
        ],
        # Phase 3 — coordinated attempt
        [
            ViolationEvent("PHONE_DETECTED",  now-30, 40, 0.97, 0.0, "object"),
            ViolationEvent("SUSTAINED_SPEECH",now-25, 20, 0.85, 4.0, "audio"),
            ViolationEvent("TAB_SWITCH",      now-20, 20, 1.00, 0.0, "browser"),
            ViolationEvent("PHONE_DETECTED",  now-15, 40, 0.99, 0.0, "object"),
            ViolationEvent("MULTI_SPEAKER",   now-10, 30, 0.82, 0.0, "audio"),
            ViolationEvent("FACE_MISMATCH",   now- 5, 40, 0.88, 0.0, "face"),
        ],
    ]

    print(f"\n  {'Phase':<10} {'Score':>8} {'Level':<12} {'P(cheat)':>10} {'Terminate?':>12}")
    print(f"  {'-'*54}")

    for i, phase_events in enumerate(phases, 1):
        det.add_events(phase_events)
        report   = det.analyze()
        snapshot = scorer.update(report)

        print(
            f"  Phase {i:<5} "
            f"{snapshot.current_score:>7.1f}  "
            f"{snapshot.risk_level:<12} "
            f"{snapshot.cheat_probability:>9.3f}  "
            f"{'YES ⚠' if snapshot.should_terminate else 'no':>10}"
        )

    print(f"\n  Peak score        : {scorer._peak_score:.1f}")
    print(f"  Final probability : {scorer.current_probability():.3f}")
    print(f"\n  Formula trace (last snapshot):")
    print(f"    R = Σ(Wi·Fi·Ci·Di)")
    print(f"    R_norm  = (R / {scorer.config.R_MAX}) × 100")
    print(f"    R_slide = α·R_prev + (1-α)·R_norm  [α={scorer.config.ALPHA}]")
    print(f"    P(cheat)= sigmoid(k=0.12, θ=55)")

    summary = scorer.get_session_summary()
    print(f"\n  Time at levels:")
    for level, secs in summary["time_at_levels"].items():
        print(f"    {level:<10}: {secs:.1f}s")
    print("─────────────────────────────────────────────────────────\n")