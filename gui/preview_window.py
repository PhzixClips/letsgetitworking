"""
The video preview window using a webview component.
"""

import tkinter as tk
from tkinter import ttk
import webbrowser
import webview
from config import COLORS

class PreviewWindow(tk.Toplevel):
    """
    A Toplevel window for previewing a video using an embedded webview.
    Includes controls for opening in browser, copying URL, and a status bar.
    """
    def __init__(self, parent, url: str, title: str, ui_call: callable):
        super().__init__(parent)
        self.url = url
        self.video_title = title
        self.ui_call = ui_call

        self.title(f"Preview • {self.video_title[:50]}...")
        self.geometry("980x620")
        self.configure(bg=COLORS.get('bg_primary', '#16181d'))

        # Center the window
        self.parent = parent
        self.parent.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        self_w = 980
        self_h = 620
        x = parent_x + (parent_w // 2) - (self_w // 2)
        y = parent_y + (parent_h // 2) - (self_h // 2)
        self.geometry(f"{self_w}x{self_h}+{x}+{y}")

        self._create_widgets()
        self._load_video()

    def _create_widgets(self):
        """Create and pack the UI components."""
        # --- Top control bar ---
        control_frame = tk.Frame(self, bg=COLORS.get('bg_secondary', '#1f232a'))
        control_frame.pack(fill='x', pady=5, padx=5)

        open_browser_btn = ttk.Button(control_frame, text="Open in Browser", command=self._open_in_browser)
        open_browser_btn.pack(side='left', padx=5)

        copy_url_btn = ttk.Button(control_frame, text="Copy URL", command=self._copy_url)
        copy_url_btn.pack(side='left', padx=5)

        reload_btn = ttk.Button(control_frame, text="Reload", command=self._reload_webview)
        reload_btn.pack(side='left', padx=5)

        close_btn = ttk.Button(control_frame, text="Close", command=self.destroy)
        close_btn.pack(side='right', padx=5)

        # --- Webview Frame ---
        self.webview_frame = tk.Frame(self, bg=COLORS.get('bg_primary', '#16181d'))
        self.webview_frame.pack(fill='both', expand=True)

        # --- Status Bar ---
        status_frame = tk.Frame(self, bg=COLORS.get('bg_secondary', '#1f232a'))
        status_frame.pack(fill='x', side='bottom')
        self.status_label = tk.Label(status_frame, text=f"Loading: {self.url}", fg=COLORS.get('fg_secondary', '#b7bdc6'), bg=COLORS.get('bg_secondary', '#1f232a'), anchor='w')
        self.status_label.pack(fill='x', padx=5, pady=2)

    def _load_video(self):
        """Load the URL into the webview component."""
        # This is a simplified embedding. Real embedding might require
        # passing a window handle, which can be complex across platforms.
        # For now, we launch it as a separate, modal-like window managed by pywebview.
        # This is consistent with the existing `_preview_video` method in the app.

        # We run webview.start in a separate thread to avoid blocking the Tkinter main loop.
        def _run_webview():
            try:
                webview.create_window(self.title(), self.url, width=960, height=580)
                webview.start(self._on_webview_error)
                # When webview.start() finishes (window is closed), schedule Toplevel destruction.
                self.ui_call(self.destroy)
            except Exception as e:
                self.ui_call(self.status_label.config, text=f"Error: {e}")
                self.ui_call(self._fallback_to_browser)

        # Start the webview in a daemon thread
        import threading
        threading.Thread(target=_run_webview, daemon=True).start()

    def _on_webview_error(self):
        """A simple error handler for the webview."""
        self.status_label.config(text="Webview closed or encountered an error.")

    def _open_in_browser(self):
        """Callback to open the URL in the default system browser."""
        try:
            webbrowser.open(self.url)
            self.status_label.config(text=f"Opened in default browser.")
        except Exception as e:
            self.status_label.config(text=f"Error: Could not open URL in browser. {e}")

    def _copy_url(self):
        """Callback to copy the URL to the clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.url)
        self.status_label.config(text=f"URL copied to clipboard!")

    def _reload_webview(self):
        """Reloads the content of the webview."""
        # This is a placeholder. Actual implementation depends on how webview is managed.
        # For pywebview, you might need to destroy and recreate the window.
        self.status_label.config(text="Reloading...")
        self.destroy()
        PreviewWindow(self.parent, self.url, self.video_title)

    def _fallback_to_browser(self):
        """Handle cases where the webview cannot load the content."""
        self.status_label.config(text="Preview blocked or failed to load. Opening in browser...")
        self._open_in_browser()
