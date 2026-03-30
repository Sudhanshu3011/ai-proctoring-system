"""
api/v1/state.py

Shared in-memory state for the API layer.
Exists to prevent circular imports between exam.py and monitoring.py.

Both files used to define or import _active_scorers from each other
causing ImportError at startup. Moving shared state here breaks the cycle.

Import pattern — use this in ALL files that need scorers/workers:
    from api.v1.state import _active_scorers, _active_workers
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_engine.risk_engine.scoring import RiskScorer
    from workers.video_worker          import VideoWorker

# ── In-memory session state ───────────────────────────────────────
# Keyed by session_id (UUID string)
# Lives for the duration of an active exam session
# Cleared in exam.py _close_session() when exam ends

_active_scorers: dict[str, "RiskScorer"]  = {}
_active_workers: dict[str, "VideoWorker"] = {}