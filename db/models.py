"""
db/models.py

All database table definitions using SQLAlchemy ORM.

Tables:
  - User         → registered candidates and admins
  - Exam         → exam configurations created by admin
  - ExamSession  → one candidate's attempt at one exam
  - Violation    → individual detected cheating events
  - RiskScore    → running risk score per session

Relationships:
  User ──< ExamSession >── Exam
  ExamSession ──< Violation
  ExamSession ──  RiskScore (one-to-one)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


# ─────────────────────────────────────────────
#  Base class
# ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────
class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN   = "admin"


class ExamStatus(str, enum.Enum):
    SCHEDULED  = "scheduled"
    ACTIVE     = "active"
    COMPLETED  = "completed"
    TERMINATED = "terminated"   # auto-terminated by risk engine


class SessionStatus(str, enum.Enum):
    PENDING    = "pending"      # registered, not started
    VERIFYING  = "verifying"    # face verification in progress
    ACTIVE     = "active"       # exam in progress
    COMPLETED  = "completed"    # submitted normally
    TERMINATED = "terminated"   # force-ended by risk engine


class ViolationType(str, enum.Enum):
    # Face module
    FACE_ABSENT   = "FACE_ABSENT"
    FACE_MISMATCH = "FACE_MISMATCH"
    MULTI_FACE    = "MULTI_FACE"
    # Head pose module
    LOOKING_AWAY  = "LOOKING_AWAY"
    # Object module
    PHONE_DETECTED     = "PHONE_DETECTED"
    BOOK_DETECTED      = "BOOK_DETECTED"
    HEADPHONE_DETECTED = "HEADPHONE_DETECTED"
    # Audio module
    SPEECH_BURST     = "SPEECH_BURST"
    SUSTAINED_SPEECH = "SUSTAINED_SPEECH"
    MULTI_SPEAKER    = "MULTI_SPEAKER"
    WHISPER          = "WHISPER"
    # Browser module
    TAB_SWITCH    = "TAB_SWITCH"
    WINDOW_BLUR   = "WINDOW_BLUR"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    COPY_PASTE    = "COPY_PASTE"


class RiskLevel(str, enum.Enum):
    SAFE     = "SAFE"       # 0–30
    WARNING  = "WARNING"    # 30–60
    HIGH     = "HIGH"       # 60–85
    CRITICAL = "CRITICAL"   # 85–100


# ─────────────────────────────────────────────
#  Helper: generate UUID string primary keys
# ─────────────────────────────────────────────
def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
#  User table
# ─────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id         = Column(String, primary_key=True, default=gen_uuid)
    email      = Column(String, unique=True, nullable=False, index=True)
    full_name  = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role       = Column(SAEnum(UserRole), default=UserRole.STUDENT, nullable=False)

    # Face embedding stored as comma-separated floats
    # In production: use pgvector extension for proper vector storage
    face_embedding = Column(Text, nullable=True)

    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    sessions = relationship("ExamSession", back_populates="user")

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


# ─────────────────────────────────────────────
#  Exam table
# ─────────────────────────────────────────────
class Exam(Base):
    __tablename__ = "exams"

    id          = Column(String, primary_key=True, default=gen_uuid)
    title       = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=60)
    status      = Column(SAEnum(ExamStatus), default=ExamStatus.SCHEDULED)

    # Risk threshold overrides (None = use global settings)
    risk_terminate_threshold = Column(Integer, nullable=True)

    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    starts_at  = Column(DateTime(timezone=True), nullable=True)
    ends_at    = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions = relationship("ExamSession", back_populates="exam")

    def __repr__(self):
        return f"<Exam '{self.title}' [{self.status}]>"


# ─────────────────────────────────────────────
#  ExamSession table
# ─────────────────────────────────────────────
class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id      = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    exam_id = Column(String, ForeignKey("exams.id"),  nullable=False)
    status  = Column(SAEnum(SessionStatus), default=SessionStatus.PENDING)

    # Timing
    started_at   = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    # Face verification result
    face_verified       = Column(Boolean, default=False)
    face_verify_score   = Column(Float,   nullable=True)   # cosine similarity

    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user       = relationship("User",       back_populates="sessions")
    exam       = relationship("Exam",       back_populates="sessions")
    violations = relationship("Violation",  back_populates="session",
                              cascade="all, delete-orphan")
    risk_score = relationship("RiskScore",  back_populates="session",
                              uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExamSession user={self.user_id} exam={self.exam_id} [{self.status}]>"


# ─────────────────────────────────────────────
#  Violation table
# ─────────────────────────────────────────────
class Violation(Base):
    __tablename__ = "violations"

    id         = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("exam_sessions.id"), nullable=False)

    violation_type = Column(SAEnum(ViolationType), nullable=False)
    weight         = Column(Integer, nullable=False)       # risk contribution
    confidence     = Column(Float,   nullable=True)        # AI model confidence
    duration_secs  = Column(Float,   nullable=True)        # how long it lasted
    description    = Column(Text,    nullable=True)

    # Evidence
    screenshot_path = Column(String, nullable=True)
    audio_path      = Column(String, nullable=True)

    timestamp  = Column(DateTime(timezone=True), default=utcnow, index=True)

    # Relationship
    session = relationship("ExamSession", back_populates="violations")

    def __repr__(self):
        return f"<Violation {self.violation_type} w={self.weight}>"


# ─────────────────────────────────────────────
#  RiskScore table
# ─────────────────────────────────────────────
class RiskScore(Base):
    __tablename__ = "risk_scores"

    id         = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("exam_sessions.id"),
                        nullable=False, unique=True)

    # Current normalized score 0–100
    current_score = Column(Float, default=0.0)
    risk_level    = Column(SAEnum(RiskLevel), default=RiskLevel.SAFE)

    # Raw weighted total before normalization
    raw_score = Column(Float, default=0.0)

    # Per-module contributions
    face_score    = Column(Float, default=0.0)
    pose_score    = Column(Float, default=0.0)
    object_score  = Column(Float, default=0.0)
    audio_score   = Column(Float, default=0.0)
    browser_score = Column(Float, default=0.0)

    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationship
    session = relationship("ExamSession", back_populates="risk_score")

    def __repr__(self):
        return f"<RiskScore {self.current_score:.1f} [{self.risk_level}]>"
