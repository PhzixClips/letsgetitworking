#!/usr/bin/env python3
"""
YouTube Clip Agent - Main Application Entry Point
"""
import sys
import os

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from gui.main_window import MainWindow
from utils.logging import setup_logging
from data.settings_manager import settings_manager
from pathlib import Path
import os

def ensure_transcripts_path_exists():
    """Create the transcripts directory if it doesn't exist."""
    transcripts_path_str = settings_manager.get('transcripts_path')
    if transcripts_path_str:
        transcripts_path = Path(transcripts_path_str)
        try:
            transcripts_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating transcripts directory at {transcripts_path}: {e}")

def main():
    """Main application entry point"""
    setup_logging()
    ensure_transcripts_path_exists()
    app = MainWindow()
    app.run()

if __name__ == '__main__':
    main()
