# gui/theme.py
# Minimal, safe theming helper that never crashes on unknown theme names.

from tkinter import ttk
from config import COLORS, UI_SCALE

def apply_theme(root, theme_name: str | None = None) -> None:
    """
    Apply a stable ttk baseline theme and respect UI scale.
    Does not depend on theme_name; uses config.COLORS which your app already imports.
    """
    # Respect scale (no-op if not supported)
    try:
        root.tk.call('tk', 'scaling', float(UI_SCALE))
    except Exception:
        pass

    # Use a reliable ttk base
    try:
        style = ttk.Style()
        # Prefer 'clam' for consistent styling across platforms
        try:
            style.theme_use('clam')
        except Exception:
            # Fall back to current default theme silently
            pass

        # Basic option database for ttk widgets to pull from
        # Keep this light; the app does more detailed styling later.
        root.option_add("*TCombobox*Listbox*Background", COLORS.get("bg_secondary", "#1f232a"))
        root.option_add("*TCombobox*Listbox*Foreground", COLORS.get("fg_primary", "#e6e6e6"))
        root.option_add("*TCombobox*Listbox*selectBackground", COLORS.get("bg_accent", "#2d6cdf"))
        root.option_add("*TCombobox*Listbox*selectForeground", COLORS.get("fg_on_accent", "#ffffff"))

    except Exception:
        # Never raise—callers already handle errors and continue with defaults
        pass
