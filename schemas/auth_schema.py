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
#  Face verification
# ─────────────────────────────────────────────
class FaceVerifyRequest(BaseModel):
    session_id:      str
    embedding_base64: str = Field(
        ...,
        description="Base64-encoded FaceNet embedding bytes"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "session_id":       "uuid-here",
            "embedding_base64": "base64encodedembedding=="
        }
    }}


class FaceVerifyResponse(BaseModel):
    verified:         bool
    similarity_score: float   # 0.0–1.0 cosine similarity
    session_id:       str
    message:          str


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
