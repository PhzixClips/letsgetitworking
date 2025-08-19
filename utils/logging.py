"""
Logging utilities for the application
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from config import LOG_PATH

def setup_logging():
    """Setup application logging"""
    # Ensure log directory exists
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_PATH),
            logging.StreamHandler()
        ]
    )

def log_upgrade(message: str) -> None:
    """
    Append a timestamped log entry to the desktop log file.
    If the log directory does not exist, it is created. Failures are silent.
    """
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, 'a', encoding='utf-8') as log_file:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_file.write(f'[{timestamp}] {message}\n')
    except Exception:
        # Silent failure as per original implementation
        pass

class Logger:
    """Simple logger class for application events"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
        log_upgrade(f"INFO: {message}")

    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
        log_upgrade(f"WARNING: {message}")

    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
        log_upgrade(f"ERROR: {message}")

    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
        log_upgrade(f"DEBUG: {message}")
