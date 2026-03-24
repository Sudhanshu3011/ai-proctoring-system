"""
ai_engine/logger.py

Centralised logger factory for all AI engine modules.
Every module calls get_logger(__name__) to get its own named logger.

All loggers share the same handlers configured here:
  - Console: colored output in dev
  - File:    JSON structured output → logs/ai_engine.log

Usage:
    from ai_engine.logger import get_logger
    logger = get_logger("face_detector")
    logger.info("Detector started")
    logger.warning("Low confidence")
    logger.error("Model load failed")
"""

import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path


# ── Log file location ─────────────────────────────────────────────
LOG_DIR  = Path("logs")
LOG_FILE = LOG_DIR / "ai_engine.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ── Formatters ────────────────────────────────────────────────────
class _ColorFormatter(logging.Formatter):
    """Colored console output for development."""
    _COLORS = {
        "DEBUG"   : "\033[36m",    # cyan
        "INFO"    : "\033[32m",    # green
        "WARNING" : "\033[33m",    # yellow
        "ERROR"   : "\033[31m",    # red
        "CRITICAL": "\033[35m",    # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color  = self._COLORS.get(record.levelname, "")
        time   = datetime.now().strftime("%H:%M:%S")
        return (
            f"{color}[{record.levelname:8s}]{self._RESET} "
            f"{time} {record.name}: {record.getMessage()}"
        )


class _JSONFormatter(logging.Formatter):
    """JSON structured logs for file output."""
    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "time"   : datetime.now(timezone.utc).isoformat(),
            "level"  : record.levelname,
            "module" : record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj)


# ── Root ai_engine logger (configured once) ───────────────────────
_root = logging.getLogger("ai_engine")
_root.setLevel(logging.DEBUG)

if not _root.handlers:
    # Console handler
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setLevel(logging.DEBUG)
    _ch.setFormatter(_ColorFormatter())
    _root.addHandler(_ch)

    # Rotating file handler
    _fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(_JSONFormatter())
    _root.addHandler(_fh)

    _root.propagate = False   # don't bubble up to root logger


def get_logger(name: str) -> logging.Logger:
    """
    Return a named child logger under the ai_engine namespace.

    Args:
        name: short module name, e.g. "face_detector", "pose_estimator"

    Returns:
        Logger named "ai_engine.<name>"
    """
    return logging.getLogger(f"ai_engine.{name}")