"""
ai_engine/face_module/recognizer.py

Face Recognition Module — AI Proctoring System

Responsibilities:
  1. Register     — store a candidate's face embedding at enrollment
  2. Verify       — compare live embedding vs stored (1:1 identity check)
  3. Search       — find best match across all registered faces (1:N)
  4. Session lock — lock verified identity to a session, re-verify on drift

Pipeline:
    Live face crop (from detector.py)
        │
        └── preprocess → InceptionResnetV1 → 512-d embedding
                │
                ├── register()  → store in registry (dict + optional file)
                ├── verify()    → cosine similarity vs stored embedding
                └── search()    → best match across all registered users

Similarity metric:
    Cosine similarity — ranges 0.0 (no match) to 1.0 (identical)
    Threshold 0.75 = industry standard for FaceNet/vggface2
    (adjustable via FaceConfig.VERIFY_THRESHOLD)

Used by:
    api/v1/auth.py     → verify-face endpoint (before exam starts)
    workers/video_worker.py → periodic re-verification during exam
"""

import os
import json
import time
import logging
import numpy as np
import torch
import cv2
import base64
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from facenet_pytorch import InceptionResnetV1

from ai_engine.logger import get_logger

# ─────────────────────────────────────────────
#  Logger
# ─────────────────────────────────────────────
logger = get_logger("face_recognizer")


# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
class FaceConfig:
    # Similarity thresholds
    VERIFY_THRESHOLD  = 0.75   # 1:1 identity verification (register vs live)
    SEARCH_THRESHOLD  = 0.70   # 1:N search minimum similarity to count as match
    DRIFT_THRESHOLD   = 0.65   # mid-exam re-verify (slightly relaxed — lighting changes)

    # Embedding dimension (InceptionResnetV1 output)
    EMBEDDING_DIM = 512

    # Registry persistence
    REGISTRY_PATH = "storage/face_registry.json"

    # Re-verification during exam
    REVERIFY_INTERVAL_SEC = 60     # re-check identity every 60 seconds
    REVERIFY_FAIL_WEIGHT  = 35     # risk score added on re-verify failure


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────
@dataclass
class RecognitionResult:
    """Returned by verify() and search()."""
    matched:     bool
    similarity:  float          # cosine similarity 0.0–1.0
    user_id:     Optional[str]  # matched user ID (None if no match)
    label:       str            # "VERIFIED" | "MISMATCH" | "UNKNOWN"
    confidence:  str            # "HIGH" | "MEDIUM" | "LOW"
    threshold:   float          # threshold used for this check


@dataclass
class RegisteredFace:
    """One registered face entry in the registry."""
    user_id:   str
    full_name: str
    embedding: np.ndarray       # (512,) float32
    registered_at: float = field(default_factory=time.time)


@dataclass
class SessionVerification:
    """Tracks identity verification state for an active exam session."""
    session_id:          str
    user_id:             str
    initial_embedding:   np.ndarray     # captured at exam start
    last_verified_at:    float = field(default_factory=time.time)
    reverify_failures:   int   = 0
    total_reverifications: int = 0


# ─────────────────────────────────────────────
#  FaceRecognizer
# ─────────────────────────────────────────────
class FaceRecognizer:
    """
    Face recognition engine — registration, verification, session locking.

    Quickstart:
        recognizer = FaceRecognizer()

        # At enrollment:
        recognizer.register(user_id="u1", full_name="Sudhanshu", embedding=emb)

        # Before exam:
        result = recognizer.verify(user_id="u1", live_embedding=live_emb)
        if result.matched:
            session = recognizer.start_session("session_1", "u1", live_emb)

        # During exam (every 60s):
        result = recognizer.reverify_session("session_1", live_emb)
    """

    def __init__(self, config: FaceConfig = None):
        self.config   = config or FaceConfig()
        self._registry: dict[str, RegisteredFace] = {}     # user_id → RegisteredFace
        self._sessions: dict[str, SessionVerification] = {} # session_id → state

        # Load persisted registry from disk if it exists
        self._load_registry()

        logger.info(
            f"FaceRecognizer ready | "
            f"registered={len(self._registry)} users | "
            f"threshold={self.config.VERIFY_THRESHOLD}"
        )

    # ─────────────────────────────────────────
    #  Core math
    # ─────────────────────────────────────────
    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """
        Cosine similarity between two L2-normalised embedding vectors.
        Returns 0.0–1.0.  1.0 = identical, 0.0 = completely different.

        FaceNet embeddings are NOT pre-normalised, so we normalise here.
        """
        a = a.flatten().astype(np.float32)
        b = b.flatten().astype(np.float32)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def _confidence_label(similarity: float, threshold: float) -> str:
        margin = similarity - threshold
        if margin >= 0.10:   return "HIGH"
        if margin >= 0.03:   return "MEDIUM"
        return "LOW"

    # ─────────────────────────────────────────
    #  Registration
    # ─────────────────────────────────────────
    def register(
        self,
        user_id:   str,
        full_name: str,
        embedding: np.ndarray,
    ) -> bool:
        """
        Store a user's face embedding.
        Call once during user enrollment (account creation).

        Args:
            user_id:   unique user ID from your User table
            full_name: display name for logging
            embedding: (512,) float32 numpy array from InceptionResnetV1

        Returns:
            True on success.
        """
        if embedding.shape != (self.config.EMBEDDING_DIM,):
            logger.error(
                f"Register failed: expected ({self.config.EMBEDDING_DIM},) "
                f"got {embedding.shape}"
            )
            return False

        self._registry[user_id] = RegisteredFace(
            user_id   = user_id,
            full_name = full_name,
            embedding = embedding.astype(np.float32),
        )
        self._save_registry()

        logger.info(f"Face registered: {full_name} (id={user_id})")
        return True

    def register_from_base64(
        self,
        user_id:          str,
        full_name:        str,
        embedding_base64: str,
    ) -> bool:
        """
        Register from base64-encoded embedding bytes
        (as returned by detector.py).

        Used by api/v1/auth.py register endpoint.
        """
        try:
            embedding_bytes = base64.b64decode(embedding_base64)
            embedding       = np.frombuffer(embedding_bytes, dtype=np.float32).copy()
            return self.register(user_id, full_name, embedding)
        except Exception as e:
            logger.error(f"register_from_base64 failed: {e}")
            return False

    def is_registered(self, user_id: str) -> bool:
        return user_id in self._registry

    def remove(self, user_id: str) -> bool:
        if user_id in self._registry:
            del self._registry[user_id]
            self._save_registry()
            logger.info(f"Face removed: user_id={user_id}")
            return True
        return False

    # ─────────────────────────────────────────
    #  1 : 1 Verification
    # ─────────────────────────────────────────
    def verify(
        self,
        user_id:        str,
        live_embedding: np.ndarray,
        threshold:      Optional[float] = None,
    ) -> RecognitionResult:
        """
        1:1 identity verification — is this live face the same
        person as the registered user?

        Used:
            - POST /api/v1/auth/verify-face  (before exam starts)
            - Mid-exam re-verification

        Args:
            user_id:        the user claiming their identity
            live_embedding: (512,) float32 from current webcam frame
            threshold:      override default if needed

        Returns:
            RecognitionResult
        """
        threshold = threshold or self.config.VERIFY_THRESHOLD

        if user_id not in self._registry:
            logger.warning(f"Verify: user_id={user_id} not in registry")
            return RecognitionResult(
                matched    = False,
                similarity = 0.0,
                user_id    = None,
                label      = "NOT_REGISTERED",
                confidence = "LOW",
                threshold  = threshold,
            )

        stored = self._registry[user_id].embedding
        sim    = self.cosine_similarity(live_embedding, stored)
        matched = sim >= threshold

        result = RecognitionResult(
            matched    = matched,
            similarity = round(sim, 4),
            user_id    = user_id if matched else None,
            label      = "VERIFIED" if matched else "MISMATCH",
            confidence = self._confidence_label(sim, threshold),
            threshold  = threshold,
        )

        logger.info(
            f"Verify | user={user_id} | "
            f"sim={sim:.4f} threshold={threshold} | "
            f"{result.label} ({result.confidence})"
        )
        return result

    def verify_from_base64(
        self,
        user_id:          str,
        embedding_base64: str,
        threshold:        Optional[float] = None,
    ) -> RecognitionResult:
        """
        Verify from base64-encoded embedding (from API request body).
        Convenience wrapper around verify() for use in routes.
        """
        try:
            embedding_bytes = base64.b64decode(embedding_base64)
            live_embedding  = np.frombuffer(
                embedding_bytes, dtype=np.float32
            ).copy()
            return self.verify(user_id, live_embedding, threshold)
        except Exception as e:
            logger.error(f"verify_from_base64 failed: {e}")
            return RecognitionResult(
                matched    = False,
                similarity = 0.0,
                user_id    = None,
                label      = "DECODE_ERROR",
                confidence = "LOW",
                threshold  = threshold or self.config.VERIFY_THRESHOLD,
            )

    # ─────────────────────────────────────────
    #  1 : N Search
    # ─────────────────────────────────────────
    def search(
        self,
        live_embedding: np.ndarray,
        threshold:      Optional[float] = None,
    ) -> RecognitionResult:
        """
        1:N search — who is this face?
        Compares against ALL registered faces and returns best match.

        Used when user_id is not known (e.g. admin face lookup,
        or detecting an unregistered person in the frame).

        Args:
            live_embedding: (512,) float32
            threshold:      minimum similarity to count as a match

        Returns:
            RecognitionResult with best match or no match
        """
        threshold = threshold or self.config.SEARCH_THRESHOLD

        if not self._registry:
            return RecognitionResult(
                matched    = False,
                similarity = 0.0,
                user_id    = None,
                label      = "REGISTRY_EMPTY",
                confidence = "LOW",
                threshold  = threshold,
            )

        best_sim     = -1.0
        best_user_id = None

        for uid, face in self._registry.items():
            sim = self.cosine_similarity(live_embedding, face.embedding)
            if sim > best_sim:
                best_sim     = sim
                best_user_id = uid

        matched = best_sim >= threshold
        user    = self._registry.get(best_user_id) if matched else None

        result = RecognitionResult(
            matched    = matched,
            similarity = round(best_sim, 4),
            user_id    = best_user_id if matched else None,
            label      = "FOUND" if matched else "UNKNOWN",
            confidence = self._confidence_label(best_sim, threshold),
            threshold  = threshold,
        )

        logger.info(
            f"Search | best={best_user_id} "
            f"sim={best_sim:.4f} | {result.label}"
        )
        return result

    # ─────────────────────────────────────────
    #  Session locking (mid-exam re-verification)
    # ─────────────────────────────────────────
    def start_session(
        self,
        session_id:       str,
        user_id:          str,
        initial_embedding: np.ndarray,
    ) -> SessionVerification:
        """
        Lock a verified identity to an exam session.
        Call this right after verify() succeeds and exam starts.

        Stores the initial embedding so mid-exam comparisons
        use the same reference frame (not a stored enrollment photo).
        """
        sv = SessionVerification(
            session_id        = session_id,
            user_id           = user_id,
            initial_embedding = initial_embedding.astype(np.float32),
        )
        self._sessions[session_id] = sv
        logger.info(
            f"Session locked | session={session_id} user={user_id}"
        )
        return sv

    def reverify_session(
        self,
        session_id:     str,
        live_embedding: np.ndarray,
    ) -> RecognitionResult:
        """
        Mid-exam identity re-verification.
        Compares current face against the initial session embedding
        (not the enrollment embedding — handles lighting/angle changes).

        Called by workers/video_worker.py every REVERIFY_INTERVAL_SEC.

        Returns:
            RecognitionResult — caller adds WEIGHT to risk engine if not matched.
        """
        if session_id not in self._sessions:
            logger.warning(f"reverify_session: unknown session={session_id}")
            return RecognitionResult(
                matched    = False,
                similarity = 0.0,
                user_id    = None,
                label      = "SESSION_NOT_FOUND",
                confidence = "LOW",
                threshold  = self.config.DRIFT_THRESHOLD,
            )

        sv  = self._sessions[session_id]
        sim = self.cosine_similarity(
            live_embedding, sv.initial_embedding
        )
        matched = sim >= self.config.DRIFT_THRESHOLD

        sv.last_verified_at  = time.time()
        sv.total_reverifications += 1
        if not matched:
            sv.reverify_failures += 1

        result = RecognitionResult(
            matched    = matched,
            similarity = round(sim, 4),
            user_id    = sv.user_id if matched else None,
            label      = "REVERIFY_OK" if matched else "REVERIFY_FAIL",
            confidence = self._confidence_label(sim, self.config.DRIFT_THRESHOLD),
            threshold  = self.config.DRIFT_THRESHOLD,
        )

        log_fn = logger.info if matched else logger.warning
        log_fn(
            f"Re-verify | session={session_id} | "
            f"sim={sim:.4f} | {result.label} | "
            f"failures={sv.reverify_failures}/{sv.total_reverifications}"
        )
        return result

    def end_session(self, session_id: str) -> dict:
        """
        End a session and return its verification summary.
        Called by exam submit / terminate.
        """
        if session_id not in self._sessions:
            return {}

        sv = self._sessions.pop(session_id)
        summary = {
            "session_id":          sv.session_id,
            "user_id":             sv.user_id,
            "total_reverifications": sv.total_reverifications,
            "reverify_failures":   sv.reverify_failures,
            "failure_rate":        round(
                sv.reverify_failures / max(sv.total_reverifications, 1), 3
            ),
        }
        logger.info(f"Session ended: {summary}")
        return summary

    # ─────────────────────────────────────────
    #  Registry persistence
    # ─────────────────────────────────────────
    def _save_registry(self):
        """
        Persist registry to JSON file.
        Embeddings stored as base64 float32 bytes.
        In production replace with pgvector / DB storage.
        """
        try:
            Path(self.config.REGISTRY_PATH).parent.mkdir(
                parents=True, exist_ok=True
            )
            data = {}
            for uid, face in self._registry.items():
                data[uid] = {
                    "user_id":       face.user_id,
                    "full_name":     face.full_name,
                    "embedding_b64": base64.b64encode(
                        face.embedding.tobytes()
                    ).decode(),
                    "registered_at": face.registered_at,
                }
            with open(self.config.REGISTRY_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def _load_registry(self):
        """Load registry from JSON file on startup."""
        path = self.config.REGISTRY_PATH
        if not os.path.exists(path):
            logger.info("No registry file found — starting fresh.")
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for uid, entry in data.items():
                embedding = np.frombuffer(
                    base64.b64decode(entry["embedding_b64"]),
                    dtype=np.float32,
                ).copy()
                self._registry[uid] = RegisteredFace(
                    user_id        = entry["user_id"],
                    full_name      = entry["full_name"],
                    embedding      = embedding,
                    registered_at  = entry.get("registered_at", 0.0),
                )
            logger.info(
                f"Registry loaded: {len(self._registry)} faces "
                f"from {path}"
            )
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")

    # ─────────────────────────────────────────
    #  Report integration
    # ─────────────────────────────────────────
    def get_session_summary(self, session_id: str) -> dict:
        """Serialisable dict for report_service.py."""
        if session_id not in self._sessions:
            return {"session_id": session_id, "error": "not found"}
        sv = self._sessions[session_id]
        return {
            "session_id":            sv.session_id,
            "user_id":               sv.user_id,
            "total_reverifications": sv.total_reverifications,
            "reverify_failures":     sv.reverify_failures,
            "failure_rate":          round(
                sv.reverify_failures / max(sv.total_reverifications, 1), 3
            ),
            "last_verified_at":      sv.last_verified_at,
        }


# ─────────────────────────────────────────────
#  Module-level singleton
# ─────────────────────────────────────────────
# Import and use this everywhere:
#   from ai_engine.face_module.recognizer import recognizer
recognizer = FaceRecognizer()


# ─────────────────────────────────────────────
#  Standalone test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os
    os.environ["QT_QPA_PLATFORM"] = "xcb"

    print("\n── FaceRecognizer standalone test ───────────────────")

    rec = FaceRecognizer()

    # Simulate two embeddings
    emb_real  = np.random.randn(512).astype(np.float32)
    emb_same  = emb_real + np.random.randn(512).astype(np.float32) * 0.05
    emb_other = np.random.randn(512).astype(np.float32)

    # Register
    rec.register("user_001", "Sudhanshu Sharma", emb_real)
    print(f"Registered: {rec.is_registered('user_001')}")

    # Verify — should match (same person, slight variation)
    r1 = rec.verify("user_001", emb_same)
    print(f"Same person : {r1.label} sim={r1.similarity} ({r1.confidence})")

    # Verify — should NOT match (different person)
    r2 = rec.verify("user_001", emb_other)
    print(f"Diff person : {r2.label} sim={r2.similarity} ({r2.confidence})")

    # Session locking
    session = rec.start_session("sess_abc", "user_001", emb_same)
    rv      = rec.reverify_session("sess_abc", emb_same)
    print(f"Re-verify   : {rv.label} sim={rv.similarity}")

    summary = rec.end_session("sess_abc")
    print(f"Session end : failures={summary['reverify_failures']}")
    print("─────────────────────────────────────────────────────\n")