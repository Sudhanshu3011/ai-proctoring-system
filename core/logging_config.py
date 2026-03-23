"""
core/logging_config.py

Structured logging setup — JSON format for production,
readable format for development.

Call setup_logging() once in main.py on startup.
Then everywhere else just use:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Something happened")
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings


# ─────────────────────────────────────────────
#  JSON formatter — for production / file logs
# ─────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    """
    Outputs each log line as a single JSON object.
    Makes logs searchable in tools like Grafana / Loki / ELK.

    Example output:
    {"time": "2025-01-01T10:00:00Z", "level": "WARNING",
     "module": "face_module.detector", "message": "Face not detected"}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "time"   : datetime.now(timezone.utc).isoformat(),
            "level"  : record.levelname,
            "module" : record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


# ─────────────────────────────────────────────
#  Human-readable formatter — for dev console
# ─────────────────────────────────────────────
class DevFormatter(logging.Formatter):
    COLORS = {
        "DEBUG"   : "\033[36m",   # cyan
        "INFO"    : "\033[32m",   # green
        "WARNING" : "\033[33m",   # yellow
        "ERROR"   : "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color  = self.COLORS.get(record.levelname, "")
        time   = datetime.now().strftime("%H:%M:%S")
        prefix = f"{color}[{record.levelname:8s}]{self.RESET}"
        return f"{prefix} {time} {record.name}: {record.getMessage()}"


# ─────────────────────────────────────────────
#  Main setup function
# ─────────────────────────────────────────────
def setup_logging():
    """
    Call once in main.py lifespan.
    Sets up:
      - Console handler (colored readable format in dev, JSON in prod)
      - Rotating file handler (JSON, 10 MB per file, 5 backups)
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Ensure log directory exists
    Path(settings.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers (prevents duplicate logs on hot-reload)
    root_logger.handlers.clear()

    # ── Console handler ───────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    if settings.APP_ENV == "development":
        console_handler.setFormatter(DevFormatter())
    else:
        console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)

    # ── Rotating file handler ─────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        filename    = settings.LOG_FILE,
        maxBytes    = 10 * 1024 * 1024,   # 10 MB per file
        backupCount = 5,
        encoding    = "utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ["uvicorn.access", "sqlalchemy.engine", "httpx"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging initialised | level={settings.LOG_LEVEL} | "
        f"env={settings.APP_ENV} | file={settings.LOG_FILE}"
    )
