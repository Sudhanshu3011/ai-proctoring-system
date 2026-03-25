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

import logging
import base64
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from ai_engine.face_module.recognizer import recognizer
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
    LoginRequest,
    LoginResponse,
    FaceVerifyRequest,
    FaceVerifyResponse,
    UserProfileResponse,
    EnrollFaceRequest,
    EnrollFaceResponse
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
# @router.post(
#     "/login",
#     response_model=LoginResponse,
#     summary="Login and receive JWT access token",
# )
# def login(payload: LoginRequest, db: Session = Depends(get_db)):
#     """
#     Validates credentials and returns a signed JWT token.
#     The token must be sent as:
#         Authorization: Bearer <token>
#     on all protected routes.
#     """
#     user = db.query(User).filter(User.email == payload.email).first()

#     # Same error for wrong email AND wrong password — prevents user enumeration
#     if not user or not verify_password(payload.password, user.hashed_password):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid email or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     if not user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Account is deactivated. Contact admin.",
#         )

#     token = create_access_token({
#         "sub":       user.email,
#         "user_id":   user.id,
#         "role":      user.role.value,
#         "full_name": user.full_name,
#     })

#     logger.info(f"Login success: {user.email}")
#     return LoginResponse(
#         access_token = token,
#         role         = user.role,
#         user_id      = user.id,
#         full_name    = user.full_name,
#         expires_in   = settings.JWT_EXPIRE_MINUTES * 60,
#     )
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
#  POST /verify-face
# ─────────────────────────────────────────────
@router.post(
    "/verify-face",
    response_model=FaceVerifyResponse,
    summary="Verify candidate identity via face embedding before exam",
)
def verify_face(
    payload: FaceVerifyRequest,
    token_data: dict  = Depends(get_current_user_payload),
    db: Session       = Depends(get_db),
):
    """
    Called by frontend right before exam starts.
    Compares live webcam embedding against stored registration embedding.

    Flow:
      1. Frontend sends base64-encoded FaceNet embedding
      2. We decode it to numpy array
      3. Compare with stored embedding using cosine similarity
      4. If similarity >= threshold → mark session as face_verified
      5. Return result to frontend

    The exam cannot proceed unless this returns verified=True.
    """
    # Get current user
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check stored embedding exists
    if not user.face_embedding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face embedding registered. Complete registration first.",
        )

    # Get exam session
    session = db.query(ExamSession).filter(
        ExamSession.id == payload.session_id,
        ExamSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")

    # Decode incoming embedding
    try:
        embedding_bytes = base64.b64decode(payload.embedding_base64)
        live_embedding  = np.frombuffer(embedding_bytes, dtype=np.float32)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid embedding format. Expected base64 float32 bytes.",
        )

    # Compare with stored embedding
    stored_embedding = str_to_embedding(user.face_embedding)
    similarity       = cosine_similarity(live_embedding, stored_embedding)
    verified         = similarity >= settings.FACE_SIMILARITY_THRESHOLD

    # Update session
    session.face_verified     = verified
    session.face_verify_score = similarity
    if verified:
        session.status = SessionStatus.ACTIVE
    db.commit()

    logger.info(
        f"Face verify | user={user.email} | "
        f"score={similarity:.3f} | verified={verified}"
    )
    return FaceVerifyResponse(
        verified         = verified,
        similarity_score = round(similarity, 4),
        session_id       = session.id,
        message          = (
            "Identity verified. Exam can start."
            if verified else
            f"Identity mismatch (score={similarity:.2f}, "
            f"threshold={settings.FACE_SIMILARITY_THRESHOLD})"
        ),
    )


# ─────────────────────────────────────────────
#  POST /enroll-face
# ─────────────────────────────────────────────
@router.post(
    "/enroll-face",
    response_model=EnrollFaceResponse,
    summary="Store face embedding for the logged-in student",
)
def enroll_face(
    payload    : EnrollFaceRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Called once per student — stores their face embedding.
    Must be called BEFORE /exams/{id}/start.
 
    Flow:
        1. Frontend / enroll_face.py captures webcam → detector.py
        2. Gets embedding_base64 from detector result
        3. POSTs here with JWT token
        4. We store embedding in DB (User.face_embedding)
        5. We register it in FaceRecognizer singleton
        6. Student can now start exams
 
    The embedding is stored as a comma-separated float string in the DB.
    The recognizer keeps it in memory for fast cosine similarity lookup.
    """
    # Get current user
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")
 
    # Decode and validate embedding
    try:
        embedding_bytes = base64.b64decode(payload.embedding_base64)
        embedding_np    = np.frombuffer(embedding_bytes, dtype=np.float32).copy()
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid embedding. Must be base64-encoded float32 bytes from detector.py"
        )
 
    # Validate dimension — FaceNet produces 512-d embeddings
    if embedding_np.shape[0] != 512:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Wrong embedding dimension: got {embedding_np.shape[0]}, expected 512"
        )
 
    # 1. Store in DB as comma-separated string
    user.face_embedding = ",".join(str(x) for x in embedding_np.tolist())
    db.commit()
 
    # 2. Register in FaceRecognizer singleton (in-memory)
    success = recognizer.register(
        user_id   = user.id,
        full_name = user.full_name,
        embedding = embedding_np,
    )
    if not success:
        raise HTTPException(500, "Failed to register face in recognizer")
 
    logger.info(f"Face enrolled | user={user.email} | dim={embedding_np.shape[0]}")
 
    return EnrollFaceResponse(
        message  = "Face enrollment successful. You can now start exams.",
        email    = user.email,
        user_id  = user.id,
        enrolled = True,
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
