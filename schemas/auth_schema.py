"""
schemas/auth_schema.py

Pydantic models for auth API request/response validation.

These are NOT database models — they define what JSON shape
the API accepts (request) and returns (response).

Pydantic validates automatically:
  - wrong field type   → 422 Unprocessable Entity
  - missing required   → 422 with clear error message
  - extra fields       → silently ignored
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from db.models import UserRole


# ─────────────────────────────────────────────
#  Register
# ─────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email:     EmailStr
    full_name: str      = Field(..., min_length=2,  max_length=100)
    password:  str      = Field(..., min_length=8,  max_length=128)
    role:      UserRole = UserRole.STUDENT

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        return v

    model_config = {"json_schema_extra": {
        "example": {
            "email":     "student@example.com",
            "full_name": "Sudhanshu Sharma",
            "password":  "Secure123",
            "role":      "student"
        }
    }}


class RegisterResponse(BaseModel):
    id:        str
    email:     str
    full_name: str
    role:      UserRole
    message:   str = "Registration successful"


# ─────────────────────────────────────────────
#  Login
# ─────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    EmailStr
    password: str

    model_config = {"json_schema_extra": {
        "example": {
            "email":    "student@example.com",
            "password": "Secure123"
        }
    }}


class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         UserRole
    user_id:      str
    full_name:    str
    expires_in:   int   # seconds

# ─────────────────────────────────────────────
#  Current user (returned by /profile)
# ─────────────────────────────────────────────
class UserProfileResponse(BaseModel):
    id:         str
    email:      str
    full_name:  str
    role:       UserRole
    is_active:  bool
    has_face_embedding: bool


# ─────────────────────────────────────────────
#  Generic error response
# ─────────────────────────────────────────────
class ErrorResponse(BaseModel):
    detail:  str
    code:    Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {"detail": "Invalid credentials", "code": "AUTH_FAILED"}
    }}

# ----------------------------------------------
#   Enroll user (face embedding)
# ----------------------------------------------

class EnrollFaceRequest(BaseModel):
    """
    Updated: accepts a sequence of frames instead of one photo.
    Frontend captures ~3 seconds of video (15-25 frames at 8 FPS).
    """
    frame_sequence: list[str] = Field(
        ...,
        min_length=8,
        description="List of base64-encoded JPEG frames captured over ~3 seconds",
    )
    fps: float = Field(
        default=8.0,
        ge=1.0,
        le=30.0,
        description="Frames per second the sequence was captured at",
    )
 
    model_config = {"json_schema_extra": {"example": {
        "frame_sequence": ["base64frame1...", "base64frame2..."],
        "fps": 8.0,
    }}}
 

class EnrollFaceResponse(BaseModel):
    message:          str
    email:            str
    user_id:          str
    enrolled:         bool
    liveness_signals: int    # 0-3: how many liveness signals passed

# ─────────────────────────────────────────────
#  Face verification
# ─────────────────────────────────────────────

class VerifyFaceRequest(BaseModel):
    """Updated: accepts frame sequence for liveness check."""
    session_id:     str
    frame_sequence: list[str] = Field(
        ...,
        min_length=8,
        description="Base64-encoded JPEG frames captured over ~3 seconds",
    )
    fps: float = Field(default=8.0, ge=1.0, le=30.0)
 
 
class VerifyFaceImageResponse(BaseModel):
    verified:          bool
    similarity_score:  float
    session_id:        str
    message:           str
    liveness_signals:  int