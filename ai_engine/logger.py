import logging
import os

# 👇 Filter to allow only DEBUG and INFO in console
class MaxLevelFilter(logging.Filter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno <= self.level


def get_logger(name: str = "ai_engine", log_file: str = "app.log"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)   # allow debug logs globally

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Create logs folder if not exists
    os.makedirs("logs", exist_ok=True)

    # File handler (kept same)
    file_handler = logging.FileHandler(os.path.join("logs", log_file))
    file_handler.setLevel(logging.INFO)

    # Console handler 👇
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.addFilter(MaxLevelFilter(logging.INFO))  
    # 👆 This ensures only DEBUG + INFO appear in console

    # Format
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger