import logging
import sys
from logging.handlers import RotatingFileHandler
import os

LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configure a console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

# Configure a rotating file handler
file_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, "app.log"),
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

def setup_logging(log_level: int = logging.INFO):
    """
    Configures the root logger and adds handlers.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicate logging
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set higher level for noisy libraries if needed
    # logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance with the specified name.
    The logger will inherit handlers from the root logger.
    """
    return logging.getLogger(name)

# Optional: Basic configuration to ensure logs are emitted if setup_logging is not called explicitly
# This is a fallback and it's better to call setup_logging() at application startup.
# logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler], format=LOG_FORMAT, datefmt=DATE_FORMAT)

