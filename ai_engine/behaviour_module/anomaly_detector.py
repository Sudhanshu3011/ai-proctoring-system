"""
ai_engine/behavior_module/anomaly_detector.py

Behavior Analysis & Anomaly Detection Module
AI-Based Intelligent Online Exam Proctoring System

Purpose:
    Sits between the 4 AI modules and the risk engine.
    Receives raw violation events from all modules and answers:
        "Is this candidate showing a PATTERN of cheating?"
        not just "did something happen once?"

Why this layer exists:
    - 1 look-away  = normal.  20 look-aways in 2 min = suspicious.
    - Phone detected once could be a false positive. Phone + tab switch
      + speech in the same 60s window = coordinated cheating attempt.
    - Single module violations are noisy. Cross-module patterns are signal.

What it does:
    1. Maintains a rolling event window (last N seconds)
    2. Detects frequency anomalies per violation type
    3. Detects cross-module co-occurrence patterns
    4. Computes per-module and overall behavior scores
    5. Outputs a BehaviorReport consumed by risk_engine/scoring.py

Input:  ViolationEvent objects from any AI module
Output: BehaviorReport with pattern flags and weighted scores

Connects to:
    ai_engine/face_module/detector.py       → FACE_ABSENT, MULTI_FACE
    ai_engine/face_module/recognizer.py     → FACE_MISMATCH
    ai_engine/head_pose_module/             → LOOKING_AWAY
    ai_engine/object_module/               → PHONE, BOOK, HEADPHONE
    ai_engine/audio_module/vad.py          → SPEECH_BURST, SUSTAINED_SPEECH
    risk_engine/scoring.py                  → consumes BehaviorReport
"""

import time
import logging
import collections
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from ai_engine.logger import get_logger

logger = get_logger("anomaly_detector")


# ─────────────────────────────────────────────
#  Violation type registry
#  Maps every violation type → base risk weight
#  These weights are used by scoring.py
# ─────────────────────────────────────────────
VIOLATION_WEIGHTS: dict[str, int] = {
    # Face module
    "FACE_ABSENT"        : 10,
    "FACE_MISMATCH"      : 40,
    "MULTI_FACE"         : 30,
    # Head pose module
    "LOOKING_AWAY"       : 15,
    # Object module
    "PHONE_DETECTED"     : 40,
    "BOOK_DETECTED"      : 25,
    "HEADPHONE_DETECTED" : 30,
    # Audio module
    "SPEECH_BURST"       : 10,
    "SUSTAINED_SPEECH"   : 20,
    "MULTI_SPEAKER"      : 30,
    "WHISPER"            :  8,
    # Browser module
    "TAB_SWITCH"         : 20,
    "WINDOW_BLUR"        : 10,
    "FULLSCREEN_EXIT"    : 15,
    "COPY_PASTE"         : 20,
}

# Module groupings — for cross-module pattern detection
MODULE_GROUPS = {
    "face"    : {"FACE_ABSENT", "FACE_MISMATCH", "MULTI_FACE"},
    "pose"    : {"LOOKING_AWAY"},
    "object"  : {"PHONE_DETECTED", "BOOK_DETECTED", "HEADPHONE_DETECTED"},
    "audio"   : {"SPEECH_BURST", "SUSTAINED_SPEECH", "MULTI_SPEAKER", "WHISPER"},
    "browser" : {"TAB_SWITCH", "WINDOW_BLUR", "FULLSCREEN_EXIT", "COPY_PASTE"},
}


# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
class BehaviorConfig:
    # Rolling window duration (seconds) for pattern analysis
    WINDOW_SECONDS = 120      # 2-minute sliding window

    # Frequency thresholds — violations per window before anomaly fires
    FREQ_THRESHOLDS: dict[str, int] = {
        "FACE_ABSENT"        : 5,
        "LOOKING_AWAY"       : 10,
        "TAB_SWITCH"         : 3,
        "WINDOW_BLUR"        : 3,
        "SPEECH_BURST"       : 4,
        "PHONE_DETECTED"     : 2,
        "BOOK_DETECTED"      : 2,
        "HEADPHONE_DETECTED" : 2,
        "SUSTAINED_SPEECH"   : 2,
        "MULTI_SPEAKER"      : 2,
        "FACE_MISMATCH"      : 1,   # even 1 is serious
        "MULTI_FACE"         : 2,
        "FULLSCREEN_EXIT"    : 2,
        "COPY_PASTE"         : 2,
        "WHISPER"            : 5,
    }

    # Co-occurrence window (seconds) — events within this gap count as related
    COOCCURRENCE_WINDOW_SEC = 30

    # Anomaly multipliers — applied to base weight when pattern detected
    FREQ_ANOMALY_MULTIPLIER   = 1.5   # repeated same violation
    COOCCUR_ANOMALY_MULTIPLIER = 2.0   # multiple modules firing together
    ESCALATION_MULTIPLIER     = 1.3   # violations increasing over time

    # Sustained behavior threshold
    # If same violation type appears in N consecutive windows → escalation
    ESCALATION_WINDOW_COUNT = 3


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────
@dataclass
class ViolationEvent:
    """
    Unified violation event — accepted from any AI module.
    All modules convert their output to this format before
    passing to the anomaly detector.
    """
    violation_type: str          # must be a key in VIOLATION_WEIGHTS
    timestamp:      float        # time.time()
    weight:         int          # base weight (from VIOLATION_WEIGHTS)
    confidence:     float = 1.0  # AI model confidence 0.0–1.0
    duration_secs:  float = 0.0  # how long the violation lasted
    source_module:  str   = ""   # "face" | "pose" | "object" | "audio" | "browser"
    description:    str   = ""


@dataclass
class AnomalyFlag:
    """A detected behavioral pattern — more serious than a single violation."""
    flag_type:   str     # FREQUENCY | COOCCURRENCE | ESCALATION | COMBINED
    description: str
    severity:    str     # LOW | MEDIUM | HIGH | CRITICAL
    multiplier:  float   # how much to scale risk weight
    modules_involved: list = field(default_factory=list)
    timestamp:   float = field(default_factory=time.time)


@dataclass
class ModuleStats:
    """Per-module violation summary for the current window."""
    module:            str
    violation_count:   int   = 0
    total_weight:      float = 0.0
    unique_types:      int   = 0
    most_frequent:     str   = ""
    anomaly_detected:  bool  = False


@dataclass
class BehaviorReport:
    """
    Output of AnomalyDetector.analyze().
    Consumed directly by risk_engine/scoring.py.
    """
    # Window stats
    window_seconds:    float
    events_in_window:  int
    timestamp:         float = field(default_factory=time.time)

    # Per-module breakdown
    module_stats:      dict = field(default_factory=dict)  # module → ModuleStats

    # Detected anomaly flags
    anomaly_flags:     list = field(default_factory=list)  # list[AnomalyFlag]

    # Aggregated scores (used by scoring.py)
    raw_behavior_score:      float = 0.0   # Σ weighted violations in window
    anomaly_multiplier:      float = 1.0   # highest active multiplier
    adjusted_behavior_score: float = 0.0   # raw × multiplier

    # Pattern flags (quick booleans for scoring.py)
    has_frequency_anomaly:    bool = False
    has_cooccurrence_anomaly: bool = False
    has_escalation:           bool = False
    active_modules_count:     int  = 0     # how many modules fired this window

    # Full session totals (cumulative, not just window)
    session_total_violations: int   = 0
    session_total_weight:     float = 0.0


# ─────────────────────────────────────────────
#  AnomalyDetector
# ─────────────────────────────────────────────
class AnomalyDetector:
    """
    Central behavior analysis engine.

    Usage in proctoring pipeline:
        detector = AnomalyDetector()

        # Each AI module feeds violations here:
        detector.add_event(ViolationEvent(
            violation_type = "LOOKING_AWAY",
            timestamp      = time.time(),
            weight         = 15,
            confidence     = 0.92,
            duration_secs  = 3.2,
            source_module  = "pose",
        ))

        # Risk engine polls this each tick:
        report = detector.analyze()
        risk_engine.update(report.adjusted_behavior_score)
    """

    def __init__(self, config: BehaviorConfig = None):
        self.config = config or BehaviorConfig()

        # All events ever recorded (full session history)
        self._all_events: list[ViolationEvent] = []

        # Session-level counters
        self._session_violation_count = 0
        self._session_total_weight    = 0.0

        # Escalation tracking — counts consecutive windows with same type
        self._consecutive_window_counts: dict[str, int] = {}

        # Previous window's violation counts (for escalation detection)
        self._prev_window_counts: dict[str, int] = {}

        logger.info(
            f"AnomalyDetector ready | "
            f"window={self.config.WINDOW_SECONDS}s"
        )

    # ─────────────────────────────────────────
    #  Event ingestion
    # ─────────────────────────────────────────
    def add_event(self, event: ViolationEvent):
        """
        Add a violation event from any AI module.
        Thread-safe for single-threaded polling loops.
        For multi-threaded workers, wrap calls with a lock.

        Args:
            event: ViolationEvent from face/pose/object/audio/browser module

        The source_module is auto-filled if not provided.
        The weight is auto-filled from VIOLATION_WEIGHTS if not provided.
        """
        # Auto-fill weight from registry if not set
        if event.weight == 0:
            event.weight = VIOLATION_WEIGHTS.get(event.violation_type, 10)

        # Auto-fill source_module from violation type
        if not event.source_module:
            for module, types in MODULE_GROUPS.items():
                if event.violation_type in types:
                    event.source_module = module
                    break

        self._all_events.append(event)
        self._session_violation_count += 1
        self._session_total_weight    += event.weight

        logger.debug(
            f"Event added | {event.violation_type} | "
            f"w={event.weight} conf={event.confidence:.2f} | "
            f"total_session={self._session_violation_count}"
        )

    def add_events(self, events: list[ViolationEvent]):
        """Batch add multiple events at once."""
        for e in events:
            self.add_event(e)

    # ─────────────────────────────────────────
    #  Window extraction
    # ─────────────────────────────────────────
    def _get_window_events(self) -> list[ViolationEvent]:
        """Return only events within the rolling window."""
        cutoff = time.time() - self.config.WINDOW_SECONDS
        return [e for e in self._all_events if e.timestamp >= cutoff]

    # ─────────────────────────────────────────
    #  Core analysis — call this each tick
    # ─────────────────────────────────────────
    def analyze(self) -> BehaviorReport:
        """
        Analyze the current rolling window and return a BehaviorReport.
        Call this each monitoring tick (every 1–5 seconds).

        Steps:
            1. Extract events in rolling window
            2. Compute per-module stats
            3. Detect frequency anomalies
            4. Detect cross-module co-occurrence patterns
            5. Detect escalation (violations increasing over time)
            6. Aggregate scores and multipliers
        """
        window_events = self._get_window_events()

        report = BehaviorReport(
            window_seconds           = self.config.WINDOW_SECONDS,
            events_in_window         = len(window_events),
            session_total_violations = self._session_violation_count,
            session_total_weight     = self._session_total_weight,
        )

        if not window_events:
            return report

        # ── Step 1: Per-module stats ──────────────────────────────
        report.module_stats       = self._compute_module_stats(window_events)
        report.active_modules_count = sum(
            1 for s in report.module_stats.values()
            if s.violation_count > 0
        )

        # ── Step 2: Raw behavior score ────────────────────────────
        report.raw_behavior_score = sum(
            e.weight * e.confidence for e in window_events
        )

        # ── Step 3: Frequency anomaly detection ───────────────────
        freq_flags = self._detect_frequency_anomalies(window_events)
        report.anomaly_flags.extend(freq_flags)
        report.has_frequency_anomaly = len(freq_flags) > 0

        # ── Step 4: Co-occurrence detection ───────────────────────
        cooc_flags = self._detect_cooccurrence(window_events)
        report.anomaly_flags.extend(cooc_flags)
        report.has_cooccurrence_anomaly = len(cooc_flags) > 0

        # ── Step 5: Escalation detection ─────────────────────────
        esc_flags = self._detect_escalation(window_events)
        report.anomaly_flags.extend(esc_flags)
        report.has_escalation = len(esc_flags) > 0

        # ── Step 6: Compute highest active multiplier ─────────────
        if report.anomaly_flags:
            report.anomaly_multiplier = max(
                f.multiplier for f in report.anomaly_flags
            )
        else:
            report.anomaly_multiplier = 1.0

        report.adjusted_behavior_score = (
            report.raw_behavior_score * report.anomaly_multiplier
        )

        if report.anomaly_flags:
            logger.warning(
                f"Anomaly detected | "
                f"flags={len(report.anomaly_flags)} | "
                f"raw={report.raw_behavior_score:.1f} | "
                f"adjusted={report.adjusted_behavior_score:.1f} | "
                f"multiplier={report.anomaly_multiplier}"
            )

        return report

    # ─────────────────────────────────────────
    #  Step 1: Per-module stats
    # ─────────────────────────────────────────
    def _compute_module_stats(
        self, events: list[ViolationEvent]
    ) -> dict[str, ModuleStats]:
        stats: dict[str, ModuleStats] = {}

        # Count per module
        for module in MODULE_GROUPS:
            module_events = [
                e for e in events if e.source_module == module
            ]
            if not module_events:
                continue

            type_counts: dict[str, int] = {}
            total_weight = 0.0
            for e in module_events:
                type_counts[e.violation_type] = (
                    type_counts.get(e.violation_type, 0) + 1
                )
                total_weight += e.weight * e.confidence

            most_frequent = max(type_counts, key=type_counts.get)

            stats[module] = ModuleStats(
                module          = module,
                violation_count = len(module_events),
                total_weight    = round(total_weight, 2),
                unique_types    = len(type_counts),
                most_frequent   = most_frequent,
            )

        return stats

    # ─────────────────────────────────────────
    #  Step 2: Frequency anomaly detection
    # ─────────────────────────────────────────
    def _detect_frequency_anomalies(
        self, events: list[ViolationEvent]
    ) -> list[AnomalyFlag]:
        """
        Check if any violation type exceeds its frequency threshold
        within the rolling window.

        Example:
            LOOKING_AWAY threshold = 10
            If candidate looked away 20 times in 2 minutes → anomaly
        """
        flags = []
        type_counts: dict[str, int] = {}

        for e in events:
            type_counts[e.violation_type] = (
                type_counts.get(e.violation_type, 0) + 1
            )

        for vtype, count in type_counts.items():
            threshold = self.config.FREQ_THRESHOLDS.get(vtype, 999)
            if count >= threshold:
                # Severity scales with how much threshold is exceeded
                ratio = count / threshold
                if ratio >= 3.0:
                    severity = "CRITICAL"
                elif ratio >= 2.0:
                    severity = "HIGH"
                elif ratio >= 1.5:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                flags.append(AnomalyFlag(
                    flag_type   = "FREQUENCY",
                    description = (
                        f"{vtype} occurred {count}x in "
                        f"{self.config.WINDOW_SECONDS}s window "
                        f"(threshold={threshold})"
                    ),
                    severity    = severity,
                    multiplier  = self.config.FREQ_ANOMALY_MULTIPLIER,
                    modules_involved = [
                        m for m, types in MODULE_GROUPS.items()
                        if vtype in types
                    ],
                ))
                logger.warning(
                    f"Frequency anomaly | {vtype} × {count} "
                    f"(threshold={threshold}) | severity={severity}"
                )

        return flags

    # ─────────────────────────────────────────
    #  Step 3: Co-occurrence detection
    # ─────────────────────────────────────────
    def _detect_cooccurrence(
        self, events: list[ViolationEvent]
    ) -> list[AnomalyFlag]:
        """
        Detect when violations from MULTIPLE MODULES fire within
        a short time window — the strongest cheating signal.

        Patterns detected:
            COORDINATED_CHEAT:  phone + speech + tab_switch together
            IMPERSONATION:      face_mismatch + audio + browser events
            ASSISTED_CHEAT:     multi_speaker + looking_away + phone

        Why this matters:
            A single phone detection could be a false positive.
            Phone + speech + tab switch in 30 seconds = coordinated attempt.
        """
        flags      = []
        cooc_window = self.config.COOCCURRENCE_WINDOW_SEC

        # Group events by 30-second sub-windows
        if not events:
            return flags

        start_time = events[0].timestamp
        end_time   = events[-1].timestamp
        step       = cooc_window

        t = start_time
        while t <= end_time:
            sub_events = [
                e for e in events
                if t <= e.timestamp < t + step
            ]

            if len(sub_events) < 2:
                t += step
                continue

            # Count unique modules firing in this sub-window
            active_modules = set(e.source_module for e in sub_events)

            if len(active_modules) >= 3:
                # 3+ modules firing together = CRITICAL
                severity   = "CRITICAL"
                multiplier = self.config.COOCCUR_ANOMALY_MULTIPLIER * 1.5
            elif len(active_modules) == 2:
                # 2 modules = HIGH
                severity   = "HIGH"
                multiplier = self.config.COOCCUR_ANOMALY_MULTIPLIER
            else:
                t += step
                continue

            vtypes = list(set(e.violation_type for e in sub_events))

            # Identify specific known dangerous patterns
            description = self._name_cooccurrence_pattern(active_modules, vtypes)

            flags.append(AnomalyFlag(
                flag_type        = "COOCCURRENCE",
                description      = description,
                severity         = severity,
                multiplier       = multiplier,
                modules_involved = list(active_modules),
            ))
            logger.warning(
                f"Co-occurrence anomaly | modules={active_modules} | "
                f"{description} | severity={severity}"
            )

            t += step

        # Deduplicate — keep highest severity only
        if len(flags) > 1:
            flags = [max(flags, key=lambda f: f.multiplier)]

        return flags

    @staticmethod
    def _name_cooccurrence_pattern(
        modules: set[str], vtypes: list[str]
    ) -> str:
        """Give a human-readable name to a co-occurrence pattern."""
        if "object" in modules and "audio" in modules:
            return (
                "Coordinated cheating attempt: "
                "external device + speech detected together"
            )
        if "face" in modules and "audio" in modules:
            return (
                "Possible impersonation: "
                "face anomaly + audio activity together"
            )
        if "pose" in modules and "audio" in modules:
            return (
                "Assisted cheating pattern: "
                "looking away + speaking simultaneously"
            )
        if "browser" in modules and "pose" in modules:
            return (
                "External resource access: "
                "tab activity + attention away from screen"
            )
        mods = " + ".join(sorted(modules))
        return f"Multi-module anomaly: {mods} active simultaneously"

    # ─────────────────────────────────────────
    #  Step 4: Escalation detection
    # ─────────────────────────────────────────
    def _detect_escalation(
        self, events: list[ViolationEvent]
    ) -> list[AnomalyFlag]:
        """
        Detect if violations are INCREASING over time within the window.
        Split window into halves — if second half has more violations
        than first half, behavior is escalating.

        This catches candidates who start cautiously and get bolder.
        """
        flags = []
        if len(events) < 4:
            return flags

        mid   = (events[0].timestamp + events[-1].timestamp) / 2
        first_half  = [e for e in events if e.timestamp <  mid]
        second_half = [e for e in events if e.timestamp >= mid]

        if not first_half or not second_half:
            return flags

        first_weight  = sum(e.weight for e in first_half)
        second_weight = sum(e.weight for e in second_half)

        # Escalation = second half is significantly heavier
        if second_weight > first_weight * 1.5 and second_weight > 20:
            flags.append(AnomalyFlag(
                flag_type   = "ESCALATION",
                description = (
                    f"Violation intensity escalating: "
                    f"first half weight={first_weight:.0f}, "
                    f"second half weight={second_weight:.0f} "
                    f"(+{((second_weight/first_weight)-1)*100:.0f}%)"
                ),
                severity    = "MEDIUM",
                multiplier  = self.config.ESCALATION_MULTIPLIER,
                modules_involved = list(
                    set(e.source_module for e in second_half)
                ),
            ))
            logger.warning(
                f"Escalation detected | "
                f"first={first_weight:.0f} → second={second_weight:.0f}"
            )

        return flags

    # ─────────────────────────────────────────
    #  Convenience: quick summary for HUD
    # ─────────────────────────────────────────
    def get_live_status(self) -> dict:
        """
        Lightweight status for admin live dashboard.
        Does not run full analysis — just window counts.
        """
        window_events = self._get_window_events()
        type_counts: dict[str, int] = {}
        for e in window_events:
            type_counts[e.violation_type] = (
                type_counts.get(e.violation_type, 0) + 1
            )

        return {
            "events_in_window"        : len(window_events),
            "session_total_violations": self._session_violation_count,
            "session_total_weight"    : round(self._session_total_weight, 1),
            "active_violation_types"  : type_counts,
            "active_modules"          : list(
                set(e.source_module for e in window_events)
            ),
        }

    # ─────────────────────────────────────────
    #  Report integration
    # ─────────────────────────────────────────
    def get_session_summary(self) -> dict:
        """Serialisable dict for report_service.py."""
        report = self.analyze()
        return {
            "session_total_violations" : self._session_violation_count,
            "session_total_weight"     : round(self._session_total_weight, 1),
            "anomaly_flags_total"      : len(report.anomaly_flags),
            "has_frequency_anomaly"    : report.has_frequency_anomaly,
            "has_cooccurrence_anomaly" : report.has_cooccurrence_anomaly,
            "has_escalation"           : report.has_escalation,
            "active_modules_count"     : report.active_modules_count,
            "adjusted_behavior_score"  : round(
                report.adjusted_behavior_score, 2
            ),
            "violation_breakdown": self.get_live_status()[
                "active_violation_types"
            ],
        }

    def reset(self):
        """Clear all events — call between exam sessions."""
        self._all_events.clear()
        self._session_violation_count = 0
        self._session_total_weight    = 0.0
        self._prev_window_counts.clear()
        logger.info("AnomalyDetector reset.")


# ─────────────────────────────────────────────
#  Module-level singleton
#  from ai_engine.behavior_module.anomaly_detector import anomaly_detector
# ─────────────────────────────────────────────
anomaly_detector = AnomalyDetector()


# ─────────────────────────────────────────────
#  Standalone test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import random

    print("\n── AnomalyDetector standalone test ─────────────────────")
    det = AnomalyDetector()
    now = time.time()

    # Simulate a suspicious exam session
    sim_events = [
        # Normal start — occasional look-away
        ViolationEvent("LOOKING_AWAY",    now - 100, 15, 0.92, 2.1, "pose"),
        ViolationEvent("LOOKING_AWAY",    now - 90,  15, 0.88, 1.8, "pose"),
        ViolationEvent("TAB_SWITCH",      now - 85,  20, 1.00, 0.0, "browser"),
        # Getting suspicious
        ViolationEvent("LOOKING_AWAY",    now - 70,  15, 0.95, 3.2, "pose"),
        ViolationEvent("SPEECH_BURST",    now - 65,  10, 0.78, 1.5, "audio"),
        ViolationEvent("LOOKING_AWAY",    now - 60,  15, 0.91, 2.8, "pose"),
        # Coordinated cheating attempt
        ViolationEvent("PHONE_DETECTED",  now - 25,  40, 0.97, 0.0, "object"),
        ViolationEvent("SUSTAINED_SPEECH",now - 22,  20, 0.85, 4.1, "audio"),
        ViolationEvent("TAB_SWITCH",      now - 20,  20, 1.00, 0.0, "browser"),
        ViolationEvent("LOOKING_AWAY",    now - 18,  15, 0.94, 2.5, "pose"),
        ViolationEvent("PHONE_DETECTED",  now - 15,  40, 0.99, 0.0, "object"),
        ViolationEvent("MULTI_SPEAKER",   now - 10,  30, 0.82, 0.0, "audio"),
    ]

    det.add_events(sim_events)
    report = det.analyze()

    print(f"\n  Events in window  : {report.events_in_window}")
    print(f"  Active modules    : {report.active_modules_count}")
    print(f"  Raw score         : {report.raw_behavior_score:.1f}")
    print(f"  Anomaly multiplier: {report.anomaly_multiplier}x")
    print(f"  Adjusted score    : {report.adjusted_behavior_score:.1f}")
    print(f"\n  Flags detected ({len(report.anomaly_flags)}):")
    for f in report.anomaly_flags:
        print(f"    [{f.severity:8s}] {f.flag_type} | {f.description}")

    print(f"\n  Module breakdown:")
    for mod, stats in report.module_stats.items():
        print(
            f"    {mod:8s} | count={stats.violation_count:2d} | "
            f"weight={stats.total_weight:5.1f} | top={stats.most_frequent}"
        )

    print(f"\n  Frequency anomaly  : {report.has_frequency_anomaly}")
    print(f"  Co-occurrence      : {report.has_cooccurrence_anomaly}")
    print(f"  Escalation         : {report.has_escalation}")
    print("─────────────────────────────────────────────────────────\n")