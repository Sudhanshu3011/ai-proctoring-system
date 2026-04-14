"""
api/v1/state.py  — UPDATED
 
Shared in-memory state for the API layer.
All session-scoped objects live here to prevent circular imports.
 
Import pattern:
    from api.v1.state import (
        _active_scorers, _active_workers,
        _gaze_trackers,  _liveness_monitors,
    )
"""
 
from typing import TYPE_CHECKING
 
if TYPE_CHECKING:
    from ai_engine.risk_engine.scoring             import RiskScorer
    from workers.video_worker                      import VideoWorker
    from ai_engine.gaze_module.gaze_tracker        import GazeTracker
    from ai_engine.face_module.continuous_liveness import ContinuousLivenessMonitor
 
# Keyed by session_id — cleared in _close_session()

_active_scorers   : dict[str, "RiskScorer"]             = {}
_active_workers   : dict[str, "VideoWorker"]            = {}
_gaze_trackers    : dict[str, "GazeTracker"]            = {}
_liveness_monitors: dict[str, "ContinuousLivenessMonitor"] = {}