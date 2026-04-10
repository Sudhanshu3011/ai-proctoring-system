"""
api/v1/auth.py

Authentication endpoints:

  POST /api/v1/auth/register     → create account
  POST /api/v1/auth/login        → get JWT token
  GET  /api/v1/auth/profile      → current user info (protected)
  POST /api/v1/auth/verify-face  → face identity check before exam
  POST /api/v1/auth/logout       → token blacklist (stateless hint)

All routes are versioned under /api/v1/auth via the router prefix
set in main.py.
"""
import json
import cv2
import torch
import logging
import base64
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from ai_engine.face_module.recognizer import recognizer,FaceRecognizer
from ai_engine.face_module.detector import preprocess_face, inception_resnet
from ai_engine.face_module.liveliness import get_liveness_checker, LivenessResult
from core.config import settings
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_payload,
)
from db.session  import get_db
from db.models   import User, ExamSession, SessionStatus
from schemas.auth_schema import (
    RegisterRequest,
    RegisterResponse,
    UserProfileResponse,
    EnrollFaceRequest,
    EnrollFaceResponse,
    VerifyFaceRequest,
    VerifyFaceImageResponse
    
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def embedding_to_str(embedding: np.ndarray) -> str:
    """Serialize numpy embedding array to comma-separated string for DB."""
    return ",".join(str(x) for x in embedding)


def str_to_embedding(s: str) -> np.ndarray:
    """Deserialize stored embedding string back to numpy array."""
    return np.array([float(x) for x in s.split(",")])


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two embedding vectors.
    Returns 1.0 = identical, 0.0 = completely different.
    Threshold in settings: FACE_SIMILARITY_THRESHOLD (default 0.75).
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def _decode_frame_sequence(frame_sequence: list[str]) -> list:
    """Decode list of base64 JPEG strings to BGR numpy arrays."""
    frames = []
    for i, b64 in enumerate(frame_sequence):
        try:
            img_bytes = base64.b64decode(b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            frame     = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is not None:
                frames.append(frame)
        except Exception as e:
            logger.debug(f"Frame {i} decode error: {e}")
    return frames
 
 

# ─────────────────────────────────────────────
#  POST /register
# ─────────────────────────────────────────────
@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Creates a new student or admin account.
    Password is bcrypt-hashed before storage — never stored plain.
    Face embedding is registered separately via /verify-face.
    """
    # Check duplicate email
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email already registered: {payload.email}",
        )

    user = User(
        email           = payload.email,
        full_name       = payload.full_name,
        hashed_password = hash_password(payload.password),
        role            = payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"New user registered: {user.email} role={user.role}")
    return RegisterResponse(
        id        = user.id,
        email     = user.email,
        full_name = user.full_name,
        role      = user.role,
    )


# ─────────────────────────────────────────────
#  POST /login
# ─────────────────────────────────────────────
@router.post("/login", summary="Login and receive JWT access token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated.")

    token = create_access_token({
        "sub":       user.email,
        "user_id":   user.id,
        "role":      user.role.value,
        "full_name": user.full_name,
    })
    logger.info(f"Login success: {user.email}")

    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role.value,
        "user_id":      user.id,
        "full_name":    user.full_name,
        "expires_in":   settings.JWT_EXPIRE_MINUTES * 60,
    }


# ─────────────────────────────────────────────
#  GET /profile
# ─────────────────────────────────────────────
@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get current logged-in user profile",
)
def get_profile(
    payload: dict = Depends(get_current_user_payload),
    db: Session   = Depends(get_db),
):
    """Protected route — requires valid JWT token."""
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(
        id                 = user.id,
        email              = user.email,
        full_name          = user.full_name,
        role               = user.role,
        is_active          = user.is_active,
        has_face_embedding = user.face_embedding is not None,
    )

# ─────────────────────────────────────────────
#  FIXED: POST /enroll-face  (multi-frame liveness)
# ─────────────────────────────────────────────
@router.post(
    "/enroll-face",
    response_model=EnrollFaceResponse,
    summary="Enroll face with multi-frame liveness detection",
)
def enroll_face(
    payload    : EnrollFaceRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Enrollment with real multi-frame liveness:
      1. Decode frame sequence from frontend
      2. Run LivenessChecker on all frames
         - Signal 1: blink cycle detected
         - Signal 2: head movement across frames
         - Signal 3: temporal texture variation
      3. Require at least 2/3 signals to pass
      4. Extract FaceNet embedding from the best (sharpest) frame
      5. Store in DB
    """
    logger.info(f"Enroll face request | user={token_data['sub']} | frames={len(payload.frame_sequence)}")   
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")
 
    # ── Decode frames ─────────────────────────────────────────────
    frames = _decode_frame_sequence(payload.frame_sequence)
    if len(frames) < 8:
        raise HTTPException(
            400,
            f"Only {len(frames)} valid frames decoded. "
            "Ensure camera is working and face is visible."
        )
 
    # ── Multi-frame liveness check ────────────────────────────────
    checker        = get_liveness_checker()
    liveness_result = checker.check(frames, fps=payload.fps)
 
    logger.info(
        f"Enroll liveness | user={user.email} | "
        f"live={liveness_result.is_live} | "
        f"signals={liveness_result.signals_passed}/3 | "
        f"blink={liveness_result.blink_detected} "
        f"move={liveness_result.head_moved} "
        f"texture={liveness_result.temporal_varied}"
    )
 
    if not liveness_result.is_live:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Liveness check failed: {liveness_result.reason} "
            f"(Passed {liveness_result.signals_passed}/3 signals: "
            f"blink={'✓' if liveness_result.blink_detected else '✗'}, "
            f"movement={'✓' if liveness_result.head_moved else '✗'}, "
            f"variation={'✓' if liveness_result.temporal_varied else '✗'})"
        )
 
    # ── Pick best frame for embedding (sharpest = highest Laplacian) ──
    best_frame = max(
        frames,
        key=lambda f: cv2.Laplacian(
            cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F
        ).var()
    )
 
    # ── Extract FaceNet embedding ─────────────────────────────────
    try:
        face_tensor  = preprocess_face(best_frame)
        with torch.no_grad():
            embedding = inception_resnet(face_tensor)
        embedding_np = embedding.cpu().numpy().flatten()
    except Exception as e:
        logger.error(f"Embedding extraction failed: {e}")
        raise HTTPException(
            500,
            "Face embedding extraction failed. "
            "Ensure your face is clearly visible and well-lit."
        )
 
    if embedding_np.shape[0] != 512:
        raise HTTPException(500, f"Wrong embedding dimension: {embedding_np.shape[0]}")
 
    # ── Store in DB ───────────────────────────────────────────────
    user.face_embedding = ",".join(f"{x:.6f}" for x in embedding_np.tolist())
    db.commit()
 
    # ── Register in recognizer ────────────────────────────────────
    success = recognizer.register(user.id, user.full_name, embedding_np)
    if not success:
        raise HTTPException(500, "Failed to register face in recognizer")
 
    logger.info(
        f"Face enrolled (multi-frame liveness) | "
        f"user={user.email} | signals={liveness_result.signals_passed}/3"
    )
    return EnrollFaceResponse(
        message          = (
            f"Face enrolled with liveness verification "
            f"({liveness_result.signals_passed}/3 signals passed)."
        ),
        email            = user.email,
        user_id          = user.id,
        enrolled         = True,
        liveness_signals = liveness_result.signals_passed,
    )
 
 
# ─────────────────────────────────────────────
#  FIXED: POST /verify-face  (multi-frame liveness)
# ─────────────────────────────────────────────
@router.post(
    "/verify-face",
    response_model=VerifyFaceImageResponse,
    summary="Verify identity before exam — multi-frame liveness required",
)
def verify_face(
    payload    : VerifyFaceRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Pre-exam verification with multi-frame liveness.
    Must pass liveness before identity comparison is even attempted.
    """
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")
 
    if not user.face_embedding:
        raise HTTPException(400, "No face enrolled. Complete enrollment first.")
 
    session = db.query(ExamSession).filter(
        ExamSession.id      == payload.session_id,
        ExamSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Exam session not found")
 
    # ── Decode frames ─────────────────────────────────────────────
    frames = _decode_frame_sequence(payload.frame_sequence)
    if len(frames) < 8:
        return VerifyFaceImageResponse(
            verified          = False,
            similarity_score  = 0.0,
            session_id        = payload.session_id,
            message           = "Not enough valid frames. Check your camera.",
            liveness_signals  = 0,
        )
 
    # ── Multi-frame liveness check ────────────────────────────────
    checker        = get_liveness_checker()
    liveness_result = checker.check(frames, fps=payload.fps)
 
    logger.info(
        f"Verify liveness | user={user.email} | "
        f"live={liveness_result.is_live} signals={liveness_result.signals_passed}/3"
    )
 
    if not liveness_result.is_live:
        return VerifyFaceImageResponse(
            verified          = False,
            similarity_score  = 0.0,
            session_id        = payload.session_id,
            message           = f"Liveness failed: {liveness_result.reason}",
            liveness_signals  = liveness_result.signals_passed,
        )
 
    # ── Pick best frame for embedding ─────────────────────────────
    best_frame = max(
        frames,
        key=lambda f: cv2.Laplacian(
            cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F
        ).var()
    )
 
    # ── Extract live embedding ────────────────────────────────────
    try:
        face_tensor   = preprocess_face(best_frame)
        with torch.no_grad():
            live_emb  = inception_resnet(face_tensor)
        live_embedding = live_emb.cpu().numpy().flatten()
    except Exception as e:
        raise HTTPException(400, f"Could not process face: {e}")
 
    # ── Cosine similarity ─────────────────────────────────────────
    stored = np.array(
        [float(x) for x in user.face_embedding.split(",")],
        dtype=np.float32,
    )
 
    def cosine_sim(a, b):
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-6 or nb < 1e-6:
            return 0.0
        return float(np.dot(a, b) / (na * nb))
 
    similarity = cosine_sim(live_embedding, stored)
    verified   = similarity >= settings.FACE_SIMILARITY_THRESHOLD
 
    # ── Update session ────────────────────────────────────────────
    session.face_verified     = verified
    session.face_verify_score = similarity
    db.commit()
 
    if verified:
        recognizer.start_session(session.id, user.id, live_embedding)
 
    logger.info(
        f"Verify-face result | user={user.email} | "
        f"sim={similarity:.3f} verified={verified} | "
        f"liveness={liveness_result.signals_passed}/3"
    )
    return VerifyFaceImageResponse(
        verified          = verified,
        similarity_score  = round(similarity, 4),
        session_id        = session.id,
        message           = (
            f"Identity verified (similarity={similarity:.2f}, "
            f"liveness={liveness_result.signals_passed}/3 signals)."
            if verified else
            f"Verification failed (similarity={similarity:.2f}, "
            f"required={settings.FACE_SIMILARITY_THRESHOLD})"
        ),
        liveness_signals  = liveness_result.signals_passed,
    )

# ─────────────────────────────────────────────
#  GET /enroll-status
# ─────────────────────────────────────────────
@router.get(
    "/enroll-status",
    summary="Check if current user has a face enrolled",
)
def enroll_status(
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Quick check before showing the 'Start Exam' button on the frontend.
    Returns enrolled=false if the student hasn't done face enrollment yet.
    """
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")
 
    enrolled    = user.face_embedding is not None
    in_memory   = recognizer.is_registered(user.id)
 
    # If enrolled in DB but not in memory (server restart), re-load it
    if enrolled and not in_memory:
        try:
            embedding_np = np.array(
                [float(x) for x in user.face_embedding.split(",")],
                dtype=np.float32,
            )
            recognizer.register(user.id, user.full_name, embedding_np)
            logger.info(f"Re-loaded face from DB | user={user.email}")
        except Exception as e:
            logger.error(f"Failed to reload face embedding: {e}")
 
    return {
        "email"    : user.email,
        "enrolled" : enrolled,
        "message"  : (
            "Face enrolled. Ready to start exam."
            if enrolled else
            "No face enrolled. Run face enrollment before starting exam."
        ),
    }
# ─────────────────────────────────────────────
#  POST /logout
# ─────────────────────────────────────────────
@router.post("/logout", summary="Logout (client should discard token)")
def logout(payload: dict = Depends(get_current_user_payload)):
    """
    JWTs are stateless — server-side blacklisting requires Redis.
    For now: instruct client to delete the token.
    Phase 2 upgrade: store token jti in Redis with TTL.
    """
    logger.info(f"Logout: {payload.get('sub')}")
    return {"message": "Logged out. Please delete your token on the client."}