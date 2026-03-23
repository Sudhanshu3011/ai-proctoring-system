"""
core/security.py

Two responsibilities:
  1. Password hashing   — bcrypt via passlib
  2. JWT tokens         — create and verify via python-jose

Used by:
  - api/v1/auth.py      (login, register)
  - api/v1/exam.py      (get current user from token)
  - Any protected route (OAuth2 dependency)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from core.config import settings

# ─────────────────────────────────────────────
#  Password hashing
# ─────────────────────────────────────────────

# bcrypt automatically salts — never store plain passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password. Call on registration."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare plain password against stored hash. Call on login."""
    return pwd_context.verify(plain_password, hashed_password)


# ─────────────────────────────────────────────
#  JWT tokens
# ─────────────────────────────────────────────

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT token.

    Args:
        data: payload dict — must include "sub" (subject = user email/id)
              e.g. {"sub": "user@email.com", "role": "student"}
        expires_delta: custom expiry — defaults to JWT_EXPIRE_MINUTES

    Returns:
        Encoded JWT string to send to client.

    Example:
        token = create_access_token({"sub": user.email, "role": user.role})
    """
    payload = data.copy()
    expire  = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Returns:
        Decoded payload dict if valid.

    Raises:
        HTTPException 401 if token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        subject: str = payload.get("sub")
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─────────────────────────────────────────────
#  FastAPI OAuth2 dependency
# ─────────────────────────────────────────────

# Tells FastAPI where clients send their token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user_payload(
    token: str = Depends(oauth2_scheme),
) -> dict:
    """
    FastAPI dependency — extracts and validates token from
    Authorization: Bearer <token> header.

    Inject into any protected route:
        @router.get("/protected")
        def protected(payload = Depends(get_current_user_payload)):
            return {"user": payload["sub"]}
    """
    return decode_access_token(token)


def require_role(required_role: str):
    """
    Role-based access dependency factory.

    Usage:
        @router.get("/admin/dashboard")
        def dashboard(payload = Depends(require_role("admin"))):
            ...
    """
    def _check(payload: dict = Depends(get_current_user_payload)):
        if payload.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {required_role}",
            )
        return payload
    return _check
