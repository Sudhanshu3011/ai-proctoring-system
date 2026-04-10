"""
audio_module/vad.py

AI-Based Intelligent Online Exam Proctoring System
Audio Monitoring Module — Hybrid VAD (WebRTC + Silero)

Pipeline per frame:
    Mic → WebRTC VAD (fast, binary, ~0.01ms)
              │
              ├── NO SPEECH → skip (Silero never runs)
              │
              └── SPEECH    → Silero VAD (neural, probability, ~2ms)
                                    │
                                    ├── prob < threshold → false positive, discard
                                    └── prob >= threshold → confirmed speech
                                                              → violation checks

Why this combination beats either alone:
  WebRTC alone  → many false positives (noise, chair scrape, AC hum)
  Silero alone  → accurate but runs on every frame (wastes CPU)
  Hybrid        → WebRTC gates 70-80% of silent frames out
                  Silero only activates on genuine audio events
                  Result: speed of WebRTC + accuracy of Silero

Detects:
  - SPEECH_BURST      — repeated talking in a short window  (weight 10)
  - SUSTAINED_SPEECH  — continuous speech > N seconds        (weight 20)
  - MULTI_SPEAKER     — rapid on/off pattern in window       (weight 30)
  - WHISPER           — low-prob speech below main threshold (weight  8)
"""

import time
import logging
import threading
import collections
import numpy as np
import torch
import webrtcvad
import pyaudio
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
#  Logger
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
class AudioConfig:
    """
    All tunable constants in one place.

    ⚠ WebRTC VAD hard requirements:
        Sample rate  : 8000 | 16000 | 32000 | 48000 Hz
        Frame duration: 10 | 20 | 30 ms  →  FRAME_MS = 30

    ⚠ Silero VAD hard requirements:
        Sample rate  : 8000 | 16000 Hz only
        Chunk samples: 512 at 16kHz  |  256 at 8kHz

    Both work at 16000 Hz / 30ms → 480 samples per chunk.
    Silero expects 512 — we zero-pad to 512 before inference.
    """

    SAMPLE_RATE         = 16000   # Hz
    CHANNELS            = 1
    FRAME_MS            = 30      # ms — WebRTC requirement
    CHUNK_SAMPLES       = int(16000 * 30 / 1000)   # = 480 samples per frame

    # ── WebRTC VAD ─────────────────────────────────────────────────
    WEBRTC_AGGRESSIVENESS = 2     # 0 (lenient) – 3 (strict)

    # ── Silero VAD ─────────────────────────────────────────────────
    SILERO_SPEECH_THRESHOLD   = 0.50   # confirmed speech
    SILERO_WHISPER_THRESHOLD  = 0.25   # whisper range

    # ── Rolling window ─────────────────────────────────────────────
    WINDOW_FRAMES = 50            # ~1.5 s at 30 ms/frame

    # ── Violation triggers ─────────────────────────────────────────
    SPEECH_RATIO_TRIGGER     = 0.60   # 60% of window → SPEECH_BURST
    SUSTAINED_SPEECH_SECONDS = 3.0
    SPEAKER_SWITCH_THRESHOLD = 8      # transitions in window → MULTI_SPEAKER
    VIOLATION_COOLDOWN       = 5.0    # seconds between same-type violations

    # ── Risk weights ───────────────────────────────────────────────
    WEIGHT_SPEECH_BURST  = 10
    WEIGHT_SUSTAINED     = 20
    WEIGHT_MULTI_SPEAKER = 30
    WEIGHT_WHISPER       = 8

    @classmethod
    def frame_bytes_pcm16(cls) -> int:
        """Bytes needed for WebRTC VAD (int16 PCM)."""
        return cls.CHUNK_SAMPLES * 2   # 2 bytes per int16 sample


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────
@dataclass
class AudioFrame:
    """Enriched frame after both VAD stages."""
    webrtc_speech: bool          # Stage 1 gate result
    silero_prob:   float         # Stage 2 Silero probability (0.0 if gated out)
    is_confirmed:  bool          # True only if both stages agree: speech
    is_whisper:    bool          # True if in whisper range


@dataclass
class AudioViolationEvent:
    timestamp:        float
    violation_type:   str     # SPEECH_BURST | SUSTAINED_SPEECH | MULTI_SPEAKER | WHISPER
    weight:           int
    duration_seconds: float = 0.0
    speech_prob:      float = 0.0
    description:      str   = ""


@dataclass
class HybridVADStats:
    # Frame counts
    total_frames:       int = 0
    webrtc_speech:      int = 0    # frames WebRTC flagged as speech
    silero_confirmed:   int = 0    # frames Silero confirmed
    silero_rejected:    int = 0    # frames WebRTC passed but Silero rejected
    frames_skipped:     int = 0    # frames WebRTC gated out (Silero never ran)

    # Violation tracking
    total_violations:     int   = 0
    violation_events:     list  = field(default_factory=list)
    last_violation_time:  dict  = field(default_factory=dict)
    speech_start_time:    Optional[float] = None
    total_speech_seconds: float = 0.0

    @property
    def silero_skip_rate(self) -> float:
        """Fraction of frames where Silero was skipped (efficiency metric)."""
        if self.total_frames == 0:
            return 0.0
        return self.frames_skipped / self.total_frames

    @property
    def false_positive_rate(self) -> float:
        """Fraction of WebRTC positives that Silero rejected."""
        if self.webrtc_speech == 0:
            return 0.0
        return self.silero_rejected / self.webrtc_speech


# ─────────────────────────────────────────────
#  Silero model singleton
# ─────────────────────────────────────────────
_silero_model = None

def _load_silero() -> torch.nn.Module:
    global _silero_model
    if _silero_model is None:
        logger.info("Loading Silero VAD model (~1 MB, cached after first run)...")
        model, _ = torch.hub.load(
            repo_or_dir  = "snakers4/silero-vad",
            model        = "silero_vad",
            force_reload = False,
            trust_repo   = True,
        )
        model.eval()
        _silero_model = model
        logger.info("Silero VAD model loaded.")
    return _silero_model


# ─────────────────────────────────────────────
#  HybridVADMonitor
# ─────────────────────────────────────────────
class HybridVADMonitor:
    """
    Two-stage hybrid Voice Activity Detector.

    Stage 1 — WebRTC VAD  : ultra-fast binary gate (skips ~75% of frames)
    Stage 2 — Silero VAD  : neural probability on WebRTC positives only

    Only frames confirmed by BOTH stages generate speech events.

    Quickstart (standalone):
        monitor = HybridVADMonitor()
        monitor.run_demo()

    Inside proctoring pipeline:
        monitor = HybridVADMonitor()
        monitor.start()

        while exam_running:
            events = monitor.poll_violations()     # never blocks
            for e in events:
                risk_engine.add(e.weight)

        monitor.stop()
        print(monitor.get_session_summary())
    """

    def __init__(self, config: AudioConfig = None):
        self.config = config or AudioConfig()
        self.stats  = HybridVADStats()

        # ── Stage 1: WebRTC VAD ────────────────────────────────────
        self.webrtc = webrtcvad.Vad(self.config.WEBRTC_AGGRESSIVENESS)

        # ── Stage 2: Silero VAD ────────────────────────────────────
        self.silero = _load_silero()

        # Rolling windows
        self._prob_window = collections.deque(maxlen=self.config.WINDOW_FRAMES)
        self._bool_window = collections.deque(maxlen=self.config.WINDOW_FRAMES)

        # Latest values for live HUD
        self._latest_prob:    float = 0.0
        self._latest_webrtc:  bool  = False

        # Thread state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock    = threading.Lock()
        self._pending: list[AudioViolationEvent] = []

        logger.info(
            f"HybridVADMonitor ready | "
            f"WebRTC aggressiveness={self.config.WEBRTC_AGGRESSIVENESS} | "
            f"Silero threshold={self.config.SILERO_SPEECH_THRESHOLD} | "
            f"{self.config.SAMPLE_RATE}Hz / {self.config.FRAME_MS}ms"
        )

    # ─────────────────────────────────────────
    #  Public control
    # ─────────────────────────────────────────
    def start(self):
        if self._running:
            logger.warning("HybridVADMonitor already running.")
            return
        self._running = True
        self._thread  = threading.Thread(
            target = self._capture_loop,
            name   = "HybridVAD",
            daemon = True,
        )
        self._thread.start()
        logger.info("HybridVADMonitor started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=4.0)
        logger.info("HybridVADMonitor stopped.")

    # ─────────────────────────────────────────
    #  Non-blocking violation poll
    # ─────────────────────────────────────────
    def poll_violations(self) -> list[AudioViolationEvent]:
        """Drain new violations. Thread-safe. Never blocks."""
        with self._lock:
            events = list(self._pending)
            self._pending.clear()
        return events

    # ─────────────────────────────────────────
    #  Live state (for HUD / admin dashboard)
    # ─────────────────────────────────────────
    def is_speech_active(self) -> bool:
        return self._latest_prob >= self.config.SILERO_SPEECH_THRESHOLD

    def is_whispering(self) -> bool:
        return (self.config.SILERO_WHISPER_THRESHOLD
                <= self._latest_prob
                < self.config.SILERO_SPEECH_THRESHOLD)

    def current_speech_prob(self) -> float:
        return round(self._latest_prob, 3)

    def current_speech_ratio(self) -> float:
        if not self._bool_window:
            return 0.0
        return sum(self._bool_window) / len(self._bool_window)

    # ─────────────────────────────────────────
    #  Two-stage frame classification
    # ─────────────────────────────────────────
    def _classify_frame(self, raw_bytes: bytes) -> AudioFrame:
        """
        Stage 1 — WebRTC VAD:
            Input : raw_bytes as int16 PCM
            Output: True/False  (fast, no ML)

        Stage 2 — Silero VAD (only if Stage 1 = True):
            Input : float32 tensor, zero-padded to 512 samples
            Output: speech probability 0.0–1.0
        """
        cfg = self.config

        # ── Stage 1: WebRTC ───────────────────────────────────────
        # WebRTC needs int16 PCM bytes
        pcm16 = self._float32_bytes_to_pcm16(raw_bytes)

        try:
            webrtc_speech = self.webrtc.is_speech(pcm16, cfg.SAMPLE_RATE)
        except Exception:
            webrtc_speech = False

        self._latest_webrtc = webrtc_speech

        if not webrtc_speech:
            # Gate passed: skip Silero entirely
            self.stats.frames_skipped += 1
            return AudioFrame(
                webrtc_speech = False,
                silero_prob   = 0.0,
                is_confirmed  = False,
                is_whisper    = False,
            )

        # ── Stage 2: Silero ───────────────────────────────────────
        self.stats.webrtc_speech += 1

        # Float32 tensor from raw bytes
        audio_np = np.frombuffer(raw_bytes, dtype=np.float32).copy()

        # Silero requires exactly 512 samples at 16kHz
        # Our chunk is 480 samples → zero-pad 32 samples
        if len(audio_np) < 512:
            audio_np = np.pad(audio_np, (0, 512 - len(audio_np)))

        audio_tensor = torch.from_numpy(audio_np[:512])

        with torch.no_grad():
            silero_prob = self.silero(audio_tensor, cfg.SAMPLE_RATE).item()

        self._latest_prob = silero_prob

        is_confirmed = silero_prob >= cfg.SILERO_SPEECH_THRESHOLD
        is_whisper   = (cfg.SILERO_WHISPER_THRESHOLD
                        <= silero_prob
                        < cfg.SILERO_SPEECH_THRESHOLD)

        if is_confirmed:
            self.stats.silero_confirmed += 1
        else:
            self.stats.silero_rejected += 1

        return AudioFrame(
            webrtc_speech = True,
            silero_prob   = silero_prob,
            is_confirmed  = is_confirmed,
            is_whisper    = is_whisper,
        )

    @staticmethod
    def _float32_bytes_to_pcm16(raw: bytes) -> bytes:
        """
        Convert pyaudio float32 bytes to int16 PCM bytes for WebRTC VAD.
        WebRTC requires int16; pyaudio captures float32 for Silero compat.
        """
        f32 = np.frombuffer(raw, dtype=np.float32)
        i16 = (f32 * 32767).clip(-32768, 32767).astype(np.int16)
        return i16.tobytes()

    # ─────────────────────────────────────────
    #  Background capture loop
    # ─────────────────────────────────────────
    def _capture_loop(self):
        cfg = self.config
        pa  = pyaudio.PyAudio()
        stream = None

        try:
            stream = pa.open(
                rate              = cfg.SAMPLE_RATE,
                channels          = cfg.CHANNELS,
                format            = pyaudio.paFloat32,
                input             = True,
                frames_per_buffer = cfg.CHUNK_SAMPLES,
            )
            logger.info("Mic opened (Hybrid VAD).")

            while self._running:
                try:
                    raw = stream.read(
                        cfg.CHUNK_SAMPLES,
                        exception_on_overflow=False,
                    )
                except OSError as e:
                    logger.warning(f"Mic read error: {e}")
                    continue

                frame = self._classify_frame(raw)
                self.stats.total_frames += 1

                # Update rolling windows with confirmed speech only
                self._prob_window.append(frame.silero_prob)
                self._bool_window.append(frame.is_confirmed)

                if frame.is_confirmed:
                    self.stats.total_speech_seconds += (
                        cfg.CHUNK_SAMPLES / cfg.SAMPLE_RATE
                    )

                # ── Violation checks ───────────────────────────────
                self._check_sustained_speech(frame)
                self._check_speech_burst(frame)
                self._check_multi_speaker()
                self._check_whisper(frame)

        except Exception as e:
            logger.error(f"Capture loop error: {e}", exc_info=True)
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()
            logger.info("Mic released.")

    # ─────────────────────────────────────────
    #  Violation checks
    # ─────────────────────────────────────────
    def _check_sustained_speech(self, frame: AudioFrame):
        """Fires after SUSTAINED_SPEECH_SECONDS of continuous confirmed speech."""
        cfg = self.config
        now = time.time()

        if frame.is_confirmed:
            if self.stats.speech_start_time is None:
                self.stats.speech_start_time = now
            else:
                duration = now - self.stats.speech_start_time
                if duration >= cfg.SUSTAINED_SPEECH_SECONDS:
                    last = self.stats.last_violation_time.get(
                        "SUSTAINED_SPEECH", 0.0
                    )
                    if (now - last) >= cfg.VIOLATION_COOLDOWN:
                        self._raise_violation(
                            vtype    = "SUSTAINED_SPEECH",
                            weight   = cfg.WEIGHT_SUSTAINED,
                            duration = round(duration, 2),
                            prob     = frame.silero_prob,
                            desc     = (
                                f"Continuous speech {duration:.1f}s "
                                f"| Silero prob={frame.silero_prob:.2f}"
                            ),
                        )
        else:
            self.stats.speech_start_time = None

    def _check_speech_burst(self, frame: AudioFrame):
        """
        Fires when avg Silero probability in rolling window
        exceeds SPEECH_RATIO_TRIGGER. Only uses Silero-confirmed
        probabilities — WebRTC false positives are already 0.0 in window.
        """
        if len(self._prob_window) < self.config.WINDOW_FRAMES:
            return

        avg_prob = float(np.mean(self._prob_window))
        if avg_prob < self.config.SPEECH_RATIO_TRIGGER:
            return

        now  = time.time()
        last = self.stats.last_violation_time.get("SPEECH_BURST", 0.0)
        if (now - last) < self.config.VIOLATION_COOLDOWN:
            return

        self._raise_violation(
            vtype    = "SPEECH_BURST",
            weight   = self.config.WEIGHT_SPEECH_BURST,
            duration = round(
                self.config.WINDOW_FRAMES
                * self.config.CHUNK_SAMPLES
                / self.config.SAMPLE_RATE, 2
            ),
            prob     = avg_prob,
            desc     = (
                f"Avg Silero prob={avg_prob:.2f} "
                f"over {self.config.WINDOW_FRAMES} frames"
            ),
        )

    def _check_multi_speaker(self):
        """
        Rapid speech/silence switching (only counting Silero-confirmed
        frames) → likely multiple speakers. Silero's accuracy means
        genuine pauses vs speaker turns are distinguished better.
        """
        if len(self._bool_window) < self.config.WINDOW_FRAMES:
            return

        frames   = list(self._bool_window)
        switches = sum(
            1 for i in range(1, len(frames))
            if frames[i] != frames[i - 1]
        )
        if switches < self.config.SPEAKER_SWITCH_THRESHOLD:
            return

        now  = time.time()
        last = self.stats.last_violation_time.get("MULTI_SPEAKER", 0.0)
        if (now - last) < self.config.VIOLATION_COOLDOWN:
            return

        self._raise_violation(
            vtype    = "MULTI_SPEAKER",
            weight   = self.config.WEIGHT_MULTI_SPEAKER,
            duration = 0.0,
            prob     = self._latest_prob,
            desc     = (
                f"Multi-speaker pattern: "
                f"{switches} transitions in window "
                f"(Silero-confirmed)"
            ),
        )

    def _check_whisper(self, frame: AudioFrame):
        """
        Catches whisper-level speech that WebRTC passed but Silero
        classified as low-probability. Only Silero can detect this.
        Uses its own lower threshold and longer cooldown.
        """
        if not frame.is_whisper:
            return

        now  = time.time()
        last = self.stats.last_violation_time.get("WHISPER", 0.0)
        if (now - last) < (self.config.VIOLATION_COOLDOWN * 2):
            return

        self._raise_violation(
            vtype    = "WHISPER",
            weight   = self.config.WEIGHT_WHISPER,
            duration = 0.0,
            prob     = frame.silero_prob,
            desc     = (
                f"Whisper detected "
                f"| Silero prob={frame.silero_prob:.2f}"
            ),
        )

    # ─────────────────────────────────────────
    #  Internal: enqueue violation
    # ─────────────────────────────────────────
    def _raise_violation(
        self,
        vtype: str,
        weight: int,
        duration: float,
        prob: float,
        desc: str,
    ):
        now   = time.time()
        event = AudioViolationEvent(
            timestamp        = now,
            violation_type   = vtype,
            weight           = weight,
            duration_seconds = duration,
            speech_prob      = round(prob, 3),
            description      = desc,
        )
        self.stats.total_violations             += 1
        self.stats.last_violation_time[vtype]    = now
        self.stats.violation_events.append(event)

        with self._lock:
            self._pending.append(event)

        logger.warning(
            f"[AUDIO VIOLATION] {vtype} | "
            f"weight={weight} | prob={prob:.2f} | "
            f"{desc} | total=#{self.stats.total_violations}"
        )

    # ─────────────────────────────────────────
    #  Risk + report integration
    # ─────────────────────────────────────────
    def get_risk_contribution(self) -> int:
        """Total weight for risk_engine/scoring.py."""
        return sum(e.weight for e in self.stats.violation_events)

    def get_session_summary(self) -> dict:
        """Serialisable dict for report_service.py."""
        total = self.stats.total_frames or 1
        return {
            "total_violations":     self.stats.total_violations,
            "risk_contribution":    self.get_risk_contribution(),
            "total_speech_seconds": round(self.stats.total_speech_seconds, 2),
            "speech_ratio_overall": round(
                self.stats.silero_confirmed / total, 3
            ),
            # ── Hybrid pipeline efficiency stats ──
            "pipeline_stats": {
                "total_frames":      self.stats.total_frames,
                "webrtc_passed":     self.stats.webrtc_speech,
                "silero_confirmed":  self.stats.silero_confirmed,
                "silero_rejected":   self.stats.silero_rejected,
                "frames_skipped":    self.stats.frames_skipped,
                "silero_skip_rate":  round(self.stats.silero_skip_rate, 3),
                "false_positive_rate": round(self.stats.false_positive_rate, 3),
            },
            "violation_events": [
                {
                    "timestamp":        e.timestamp,
                    "type":             e.violation_type,
                    "weight":           e.weight,
                    "duration_seconds": e.duration_seconds,
                    "speech_prob":      e.speech_prob,
                    "description":      e.description,
                }
                for e in self.stats.violation_events
            ],
        }

