# api/v1/room.py

"""
POST /api/v1/exam/{exam_id}/room-scan

Request:
{
    "session_id": "uuid",
    "frames": ["base64...", "base64...", ...]
}

Response:
RoomScanResult.to_dict()
"""

import base64
import logging
import numpy as np
import cv2

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.security import get_current_user_payload
from db.session import get_db
from db.models import ExamSession, SessionStatus

from ai_engine.room_module.room_scan import RoomScanner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/room", tags=["Room Scan"])


# ─────────────────────────────────────────────
# Request Schema
# ─────────────────────────────────────────────
class RoomScanRequest(BaseModel):
    session_id: str
    frames: list[str] = Field(..., description="List of base64 encoded frames (20–40 frames)")


# ─────────────────────────────────────────────
# Helpers (same pattern as monitoring.py)
# ─────────────────────────────────────────────
def _get_active_session(session_id: str, db: Session) -> ExamSession:
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.status == SessionStatus.ACTIVE,
    ).first()

    if not session:
        raise HTTPException(404, "Active session not found")

    return session


def _decode_frames(frames_b64: list[str]) -> list[np.ndarray]:
    decoded_frames = []

    for idx, frame_b64 in enumerate(frames_b64):
        try:
            img_bytes = base64.b64decode(frame_b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if frame is None:
                raise ValueError("Invalid image decode")

            decoded_frames.append(frame)

        except Exception as e:
            logger.error(f"Frame decode failed at index {idx}: {e}")
            continue

    if len(decoded_frames) < 5:
        raise HTTPException(400, "Not enough valid frames for room scan")

    return decoded_frames


# ─────────────────────────────────────────────
# POST /room-scan
# ─────────────────────────────────────────────
@router.post(
    "/exam/{exam_id}/room-scan",
    summary="Run pre-exam room environment scan",
)
def room_scan(
    exam_id: str,
    payload: RoomScanRequest,
    token_data: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """
    Similar flow as monitoring/frame:
    1. Validate session
    2. Decode frames
    3. Run AI module
    4. Return structured result
    """

    # ── Step 1: Validate session ─────────────────────
    session = _get_active_session(payload.session_id, db)

    if str(session.exam_id) != str(exam_id):
        raise HTTPException(403, "Session does not belong to this exam")

    # ── Step 2: Decode frames ────────────────────────
    frames = _decode_frames(payload.frames)

    # ── Step 3: Run Room Scanner ─────────────────────
    try:
        scanner = RoomScanner()
        result = scanner.analyse(frames)

    except Exception as e:
        logger.error(f"Room scan failed: {e}")
        raise HTTPException(500, "Room scan processing failed")

    # ── Step 4: Optional DB logging (recommended) ────
    # You can later store findings in DB if needed

    # ── Step 5: Return result ────────────────────────
    return result.to_dict()