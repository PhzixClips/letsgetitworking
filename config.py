"""
Configuration and constants for YouTube Clip Agent
"""

import os
from pathlib import Path
from data.settings_manager import settings_manager

# -----------------------------
# API Configuration
# -----------------------------
API_KEY_LIST = settings_manager.get("api_keys", [])

# -----------------------------
# File paths
# -----------------------------
PRESETS_FILE = "presets.json"
FRAMES_DIR_NAME = "frames"
AUDIO_FILE_NAME = "audio.wav"

LOG_PATH = Path(settings_manager.get("log_path", "."))
AUDIO_CLIPS_PATH = Path(settings_manager.get("audio_clips_path", "."))
CLIPHUSTLE_BASE_PATH = Path(settings_manager.get("cliphustle_base_path", "."))

# -----------------------------
# External tool paths
# -----------------------------
YT_DLP_PATH = settings_manager.get("yt_dlp_path")
FFMPEG_PATH = settings_manager.get("ffmpeg_path")

# -----------------------------
# Search configuration
# -----------------------------
MAX_API_CALLS = settings_manager.get("max_api_calls", 100)
MIN_RESULTS_PER_CALL = settings_manager.get("min_results_per_call", 3)
DEFAULT_SEARCH_COUNT = settings_manager.get("default_search_count", 50)
DEFAULT_MAX_RESULTS_PER_QUERY = settings_manager.get("default_max_results_per_query", 50)

# -----------------------------
# Window & layout
# -----------------------------
WINDOW_GEOMETRY = settings_manager.get("window_geometry", "1200x700")
TAB_HEIGHT = 50

# Optional global UI knobs (used by future theming/styling)
UI_FONT_FAMILY = settings_manager.get("font_family", "Segoe UI")
UI_FONT_SIZES = settings_manager.get("font_sizes", {"base": 10, "sm": 9, "lg": 12, "xl": 14})
UI_SPACING = {
    "xs": 2,
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 16,
}
UI_RADIUS = 10  # recommended corner radius for custom widgets

# Optional DPI/scale override (used by theme if available)
UI_SCALE = settings_manager.get("ui_scale", 1.0)

# -------------------------------------------------------------------
# THEME SYSTEM
# -------------------------------------------------------------------
# Pick the active theme by name. You can override via env var YCA_THEME.
THEME_NAME = os.getenv("YCA_THEME", settings_manager.get("theme_name", "onyx"))

# Each theme must define this set of keys. If any are missing, we will
# backfill from the 'onyx' defaults below.
_THEMES = {
    # Modern dark (default)
    "onyx": {
        "bg_primary":   "#16181d",
        "bg_secondary": "#1f232a",
        "bg_tertiary":  "#2a2f37",
        "bg_accent":    "#3b82f6",   # blue accent
        "fg_primary":   "#e6e6e6",
        "fg_secondary": "#b7bdc6",
        "fg_accent":    "#fbbf24",   # amber text accent
        "fg_success":   "#22c55e",
        "fg_warning":   "#f59e0b",
        "fg_error":     "#ef4444",
        "button_bg":    "#2f3540",
        "button_danger":"#dc2626",
        "border":       "#39414d",
        "hover":        "#323845",
        "focus_ring":   "#60a5fa",
        "muted":        "#9aa3af",
    },

    # Neon highlight variant
    "neon": {
        "bg_primary":   "#0f1115",
        "bg_secondary": "#171a21",
        "bg_tertiary":  "#1f2430",
        "bg_accent":    "#10b981",  # teal
        "fg_primary":   "#e5e7eb",
        "fg_secondary": "#a3a3a3",
        "fg_accent":    "#34d399",
        "fg_success":   "#22c55e",
        "fg_warning":   "#f59e0b",
        "fg_error":     "#ef4444",
        "button_bg":    "#2a303c",
        "button_danger":"#b91c1c",
        "border":       "#2f3746",
        "hover":        "#2b3340",
        "focus_ring":   "#10b981",
        "muted":        "#94a3b8",
    },

    # High-contrast accessibility
    "high_contrast": {
        "bg_primary":   "#000000",
        "bg_secondary": "#111111",
        "bg_tertiary":  "#1a1a1a",
        "bg_accent":    "#ffd400",
        "fg_primary":   "#ffffff",
        "fg_secondary": "#e5e5e5",
        "fg_accent":    "#ffd400",
        "fg_success":   "#00ff6a",
        "fg_warning":   "#ffae00",
        "fg_error":     "#ff3b30",
        "button_bg":    "#222222",
        "button_danger":"#ff3b30",
        "border":       "#3a3a3a",
        "hover":        "#2a2a2a",
        "focus_ring":   "#ffd400",
        "muted":        "#cfcfcf",
    },

    # Light mode, if you ever want it
    "light": {
        "bg_primary":   "#f7f7f9",
        "bg_secondary": "#ffffff",
        "bg_tertiary":  "#eef0f4",
        "bg_accent":    "#2563eb",
        "fg_primary":   "#1f2937",
        "fg_secondary": "#4b5563",
        "fg_accent":    "#111827",
        "fg_success":   "#16a34a",
        "fg_warning":   "#d97706",
        "fg_error":     "#dc2626",
        "button_bg":    "#e5e7eb",
        "button_danger":"#ef4444",
        "border":       "#cbd5e1",
        "hover":        "#e2e8f0",
        "focus_ring":   "#2563eb",
        "muted":        "#6b7280",
    },
}

# Resolve palette with sensible fallbacks.
def _resolve_palette(name: str) -> dict:
    base = dict(_THEMES["onyx"])
    chosen = _THEMES.get(name, {})
    base.update(chosen)
    return base

# Public color map used throughout the app (keeps old name for compatibility)
COLORS = _resolve_palette(THEME_NAME)

# Also expose the theme map under the public name expected by gui.theme
THEMES = _THEMES  # <-- added alias for theme.py

# -------------------------------------------------------------------
# Viral score weights (unchanged)
# -------------------------------------------------------------------
VIRAL_SCORE_WEIGHTS = settings_manager.get("viral_score_weights", {})

# -------------------------------------------------------------------
# Cross-platform keywords for repost detection
# -------------------------------------------------------------------
REPOST_KEYWORDS = settings_manager.get("repost_keywords", [])

# -------------------------------------------------------------------
# Generic hashtags for content generation
# -------------------------------------------------------------------
GENERIC_HASHTAGS = settings_manager.get("generic_hashtags", [])
