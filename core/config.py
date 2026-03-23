"""
core/config.py

Central configuration — reads from .env file.
Every other module imports settings from here.
Never hardcode secrets anywhere else.

Usage:
    from core.config import settings
    print(settings.DATABASE_URL)
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """
    All settings read from environment variables or .env file.
    Pydantic validates types automatically on startup.
    Wrong type = crash at boot, not a silent runtime bug.
    """

    # ── App ───────────────────────────────────────────────────────
    APP_NAME:  str  = "AI Proctoring System"
    APP_ENV:   str  = "development"
    APP_DEBUG: bool = True
    APP_HOST:  str  = "0.0.0.0"
    APP_PORT:  int  = 8000

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/proctoring_db",
        description="Full PostgreSQL connection string"
    )

    # ── JWT ───────────────────────────────────────────────────────
    JWT_SECRET_KEY:     str = Field(
        default="change-this-secret-in-production",
        description="MUST be changed before production deploy"
    )
    JWT_ALGORITHM:      str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # ── CORS ──────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # ── Face Recognition ──────────────────────────────────────────
    FACE_SIMILARITY_THRESHOLD: float = 0.75   # cosine similarity cutoff

    # ── Storage directories ───────────────────────────────────────
    STORAGE_DIR:     str = "storage"
    SCREENSHOTS_DIR: str = "storage/screenshots"
    REPORTS_DIR:     str = "storage/reports"

    # ── Logging ───────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE:  str = "logs/app.log"

    # ── Risk engine thresholds ────────────────────────────────────
    RISK_WARN_THRESHOLD:     int = 30
    RISK_HIGH_THRESHOLD:     int = 60
    RISK_CRITICAL_THRESHOLD: int = 85

    def create_dirs(self):
        """Create all required directories on startup."""
        for d in [self.STORAGE_DIR, self.SCREENSHOTS_DIR,
                  self.REPORTS_DIR, "logs"]:
            Path(d).mkdir(parents=True, exist_ok=True)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — created once, reused everywhere."""
    return Settings()


# Convenience import: from core.config import settings
settings = get_settings()
