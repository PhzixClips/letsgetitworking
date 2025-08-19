"""
Settings Manager for the YouTube Clip Agent

Handles loading, saving, and providing access to user-configurable settings
persisted in a JSON file.
"""

import json
from pathlib import Path
import os

class SettingsManager:
    """
    Manages application settings, loading from and saving to a JSON file.
    """
    def __init__(self, settings_file: str = 'settings.json'):
        self.settings_path = Path(settings_file)
        self.settings = {}
        self.load_settings()

    def get_defaults(self) -> dict:
        """
        Returns a dictionary of default settings. These are based on the original
        config.py file.
        """
        """
        Returns a dictionary of default settings. These are based on the original
        config.py file.
        """
        # Determine the default transcripts path
        appdata_path = os.getenv('APPDATA')
        if appdata_path:
            transcripts_path = str(Path(appdata_path) / "ViralSniper" / "Transcripts")
        else:
            # Fallback to a local folder if APPDATA is not available
            transcripts_path = str(Path.cwd() / "transcripts")

        return {
            # API & Paths
            "api_keys": [
                "AIzaSyAPkOpyEFhiYqBTOWDYp6UnCZPnH-lFI",
                "AIzaSyAPkOpyEFhiYqmnVoVuf4haQMCFr-NZTVvNUs",
                "AIzaSyBCBWsJw817Bor6K62IgoM64f-EABm4rXg",
                "AIzaSyCBlmnUspk4fp6nT81gJbcSz6SnMwPSkmQ",
            ],
            "yt_dlp_path": "C:\\yt-dlp\\yt-dlp.exe",
            "ffmpeg_path": "ffmpeg",
            "log_path": str(Path.home() / "OneDrive" / "Desktop" / "upgrade_log.txt"),
            "audio_clips_path": str(Path.home() / "OneDrive" / "Desktop" / "audio_clips"),
            "cliphustle_base_path": str(Path.home() / "Desktop" / "ClipHustle"),
            "transcripts_path": transcripts_path,

            # Appearance
            "theme_name": "onyx",
            "ui_scale": 1.0,
            "font_family": "Segoe UI",
            "font_sizes": {
                "base": 10,
                "sm": 9,
                "lg": 12,
                "xl": 14,
            },

            # Search & Analysis
            "max_api_calls": 100,
            "default_search_count": 50,
            "min_results_per_call": 3,
            "default_max_results_per_query": 50,
            "viral_score_weights": {
                "momentum": 0.45,
                "engagement": 0.25,
                "short_bonus": 0.10,
                "polarity": 0.10,
                "trend_flag": 0.10,
            },
            "repost_keywords": [
                "tiktok", "instagram", "facebook", "reels", "shorts",
                "original by", "credit:", "repost", "ig", "tiktoks", "insta"
            ],
            "generic_hashtags": ["#viral", "#trending", "#fyp", "#mustwatch", "#explore"],

            # Window
            "window_geometry": "1200x700",

            # Save Dialog
            "save_default_folder": "Default",
            "save_auto_open_prompt_builder": False,
            "save_auto_download_transcript": False,
            "save_remember_last_folder": True,
            "save_last_used_folder": "Default"
        }

    def load_settings(self):
        """
        Loads settings from the JSON file. If the file doesn't exist, it's
        created with default values. If it exists, it's loaded and merged
        with defaults to ensure all keys are present.
        """
        defaults = self.get_defaults()
        if not self.settings_path.exists():
            self.settings = defaults
            self.save_settings()
            return

        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                user_settings = json.load(f)

            # Merge user settings with defaults to ensure all keys are present
            self.settings = self._merge_dicts(defaults, user_settings)

        except (json.JSONDecodeError, TypeError):
            # If file is corrupted or not a dict, fallback to defaults
            self.settings = defaults

        self.save_settings() # Save to normalize file and add any new keys

    def save_settings(self):
        """Saves the current settings to the JSON file."""
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        """Retrieves a setting value by key."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Sets a setting value by key and saves it."""
        self.settings[key] = value
        self.save_settings()

    def _merge_dicts(self, base, override):
        """
        Recursively merges two dictionaries. The `override` dict's values
        take precedence.
        """
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                base[key] = self._merge_dicts(base[key], value)
            else:
                base[key] = value
        return base

# Global instance to be used across the application
settings_manager = SettingsManager()
