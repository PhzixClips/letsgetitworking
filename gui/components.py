# gui/components.py
"""
Reusable GUI components and widgets
(Do not rename this module.)
"""

from typing import Optional, Callable, List, Dict, Any
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Toplevel
from pathlib import Path

# COLORS may come from your app's config; fall back to palette if missing
try:
    from config import COLORS  # type: ignore
except Exception:
    COLORS = {}

# ---- Theme & UX Helpers -----------------------------------------------------

PALETTE = {
    "bg": "#0f1115",
    "bg2": "#161a22",
    "card": "#141922",
    "border": "#232a36",
    "text": "#e6edf3",
    "muted": "#9aa4b2",
    "accent": "#7c5cff",
    "accent_hover": "#8a6dff",
    "accent_active": "#6a4dff",
    "ok": "#00d389",
    "warning": "#ffad33",
    "danger": "#ff5d5d",
}


def install_style(root: tk.Misc) -> None:
    """
    Apply a cohesive dark theme to ttk widgets and the given root/toplevel.
    Hardened so inputs are readable even on Windows themes that ignore defaults.
    """
    try:
        style = ttk.Style()
        try:
            style.theme_use("clam")  # reliable, skinnable on Windows
        except Exception:
            pass

        # Option DB: ensure combobox dropdown list is dark too
        try:
            # These affect the popdown Listbox colors
            root.option_add('*TCombobox*Listbox.background', PALETTE["bg2"])
            root.option_add('*TCombobox*Listbox.foreground', PALETTE["text"])
            root.option_add('*TCombobox*Listbox.selectBackground', PALETTE["accent"])
            root.option_add('*TCombobox*Listbox.selectForeground', 'white')
        except Exception:
            pass

        if isinstance(root, (tk.Tk, tk.Toplevel)):
            root.configure(bg=PALETTE["bg"])

        # Containers
        style.configure("TFrame", background=PALETTE["bg"])
        style.configure("Card.TFrame", background=PALETTE["card"], borderwidth=1, relief="solid")

        # Labels
        style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"])
        style.configure("Muted.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"])
        style.configure("Section.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"],
                        font=("Segoe UI Semibold", 10))

        # Buttons
        style.configure("Accent.TButton", background=PALETTE["accent"], foreground="white",
                        borderwidth=0, padding=(12, 8))
        style.map("Accent.TButton",
                  background=[("active", PALETTE["accent_hover"]), ("pressed", PALETTE["accent_active"])])

        style.configure("Ghost.TButton", background=PALETTE["bg2"], foreground=PALETTE["text"],
                        borderwidth=1, relief="solid", padding=(12, 8))
        style.map("Ghost.TButton",
                  background=[("active", PALETTE["bg"]), ("pressed", PALETTE["bg"])])

        # Inputs — global (good defaults)
        style.configure("TEntry",
                        fieldbackground=PALETTE["bg2"],
                        background=PALETTE["bg2"],
                        foreground=PALETTE["text"],
                        bordercolor=PALETTE["border"])
        style.map("TEntry",
                  fieldbackground=[("!disabled", PALETTE["bg2"]), ("disabled", PALETTE["bg2"])],
                  foreground=[("!disabled", PALETTE["text"]), ("disabled", PALETTE["muted"])])

        style.configure("TCombobox",
                        fieldbackground=PALETTE["bg2"],
                        background=PALETTE["bg2"],
                        foreground=PALETTE["text"],
                        arrowcolor=PALETTE["muted"],
                        bordercolor=PALETTE["border"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", PALETTE["bg2"]), ("!disabled", PALETTE["bg2"])],
                  foreground=[("readonly", PALETTE["text"]), ("!disabled", PALETTE["text"])],
                  background=[("readonly", PALETTE["bg2"]), ("!disabled", PALETTE["bg2"])])

        # Inputs — explicit DARK variants (used by Prompt Builder to defeat stubborn themes)
        style.configure("Dark.TEntry",
                        fieldbackground=PALETTE["bg2"],
                        background=PALETTE["bg2"],
                        foreground=PALETTE["text"],
                        bordercolor=PALETTE["border"])
        style.map("Dark.TEntry",
                  fieldbackground=[("focus", PALETTE["bg2"]), ("!disabled", PALETTE["bg2"])],
                  foreground=[("focus", PALETTE["text"]), ("!disabled", PALETTE["text"])])

        style.configure("Dark.TCombobox",
                        fieldbackground=PALETTE["bg2"],
                        background=PALETTE["bg2"],
                        foreground=PALETTE["text"],
                        arrowcolor=PALETTE["muted"],
                        bordercolor=PALETTE["border"])
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", PALETTE["bg2"]), ("!disabled", PALETTE["bg2"])],
                  foreground=[("readonly", PALETTE["text"]), ("!disabled", PALETTE["text"])],
                  background=[("readonly", PALETTE["bg2"]), ("!disabled", PALETTE["bg2"])])

        # Slider
        style.configure("Horizontal.TScale", background=PALETTE["bg"])
    except Exception:
        pass


def style_text_widget(widget: tk.Text) -> None:
    """Apply monospaced card styling to a tk.Text widget."""
    try:
        widget.configure(
            bg=PALETTE["card"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["text"],
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
            highlightcolor=PALETTE["accent"],
            padx=10,
            pady=10,
            wrap="word",
            font=("Consolas", 10),
        )
    except Exception:
        pass


def show_toast(anchor_widget: tk.Misc, text: str = "Copied ✓", ms: int = 1400,
               color: str = PALETTE["ok"]) -> None:
    """Small floating confirmation bubble near the given widget."""
    try:
        w = Toplevel(anchor_widget)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=color)
        lbl = tk.Label(w, text=text, bg=color, fg="#0b1b13",
                       font=("Segoe UI Semibold", 9), padx=10, pady=6)
        lbl.pack()
        x = anchor_widget.winfo_rootx() + 12
        y = anchor_widget.winfo_rooty() + 12
        w.geometry(f"+{x}+{y}")

        def _fade(step: int = 1) -> None:
            try:
                alpha = max(0.0, 1.0 - step * 0.1)
                w.attributes("-alpha", alpha)
                if alpha > 0:
                    w.after(60, _fade, step + 1)
                else:
                    w.destroy()
            except Exception:
                pass

        w.after(ms, _fade)
    except Exception:
        pass


# ---- Tooltip ---------------------------------------------------------------

class Tooltip:
    """Simple tooltip widget for displaying hover text."""

    def __init__(self) -> None:
        self.tipwindow: Optional[tk.Toplevel] = None

    def show(self, text: str, x: int, y: int) -> None:
        """Show tooltip at screen coordinates (x, y)."""
        self.hide()
        tw = tk.Toplevel()
        self.tipwindow = tw
        tw.wm_overrideredirect(True)
        tw.configure(bg=COLORS.get('bg_secondary', PALETTE["bg2"]))

        label = tk.Label(
            tw,
            text=text,
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            bg=COLORS.get('bg_secondary', PALETTE["bg2"]),
            justify='left',
            relief='solid',
            borderwidth=1,
            font=('Segoe UI', 8)
        )
        label.pack(ipadx=4, ipady=2)
        tw.wm_geometry(f"+{x + 20}+{y + 15}")

    def hide(self) -> None:
        if self.tipwindow:
            try:
                self.tipwindow.destroy()
            except Exception:
                pass
            self.tipwindow = None


def bind_tooltip(widget: tk.Widget, arg2, arg3: Optional[Callable] = None) -> Tooltip:
    """
    Flexible tooltip binder to maintain backward compatibility.
    """
    if isinstance(arg2, Tooltip):
        tip = arg2
        text_provider = arg3
    else:
        tip = Tooltip()
        text_provider = arg2  # could be str or callable

    def _get_text(e):
        if callable(text_provider):
            try:
                return text_provider(e)
            except TypeError:
                try:
                    return text_provider()
                except Exception:
                    return ""
        return str(text_provider)

    def _enter(e):
        try:
            txt = _get_text(e)
            if txt:
                tip.show(txt, e.x_root, e.y_root)
        except Exception:
            pass

    def _motion(e):
        if tip.tipwindow:
            try:
                tip.tipwindow.wm_geometry(f"+{e.x_root + 20}+{e.y_root + 15}")
            except Exception:
                pass

    def _leave(_e):
        tip.hide()

    widget.bind("<Enter>", _enter, add="+")
    widget.bind("<Motion>", _motion, add="+")
    widget.bind("<Leave>", _leave, add="+")
    return tip


# ---- Progress Dialog --------------------------------------------------------

class ProgressDialog:
    """Progress dialog for long-running operations."""

    def __init__(self, parent: tk.Tk, title: str, width: int = 450, height: int = 220) -> None:
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        try:
            install_style(self.window)
        except Exception:
            pass
        self.window.geometry(f"{width}x{height}")
        self.window.configure(bg=COLORS.get('bg_secondary', PALETTE["bg2"]))
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.lift()
        self.window.attributes('-topmost', True)

        self._center_window(width, height)

        self.title_label = tk.Label(
            self.window,
            text=title,
            fg=COLORS.get('fg_accent', PALETTE["accent"]),
            bg=COLORS.get('bg_secondary', PALETTE["bg2"]),
            font=('Segoe UI', 13, 'bold')
        )
        self.title_label.pack(pady=(12, 6))

        self.status_label = tk.Label(
            self.window,
            text="Starting...",
            bg=COLORS.get('bg_secondary', PALETTE["bg2"]),
            fg=COLORS.get('fg_success', "#1dd1a1"),
            font=('Arial', 12, 'bold')
        )
        self.status_label.pack(pady=15)

        self.progress_info = tk.Label(
            self.window,
            text="Initializing...",
            bg=COLORS.get('bg_secondary', PALETTE["bg2"]),
            fg=COLORS.get('fg_warning', PALETTE["warning"]),
            font=('Segoe UI', 10)
        )
        self.progress_info.pack()

        self._create_progress_bar()

        button_frame = tk.Frame(self.window, bg=COLORS.get('bg_secondary', PALETTE["bg2"]))
        button_frame.pack(pady=15)

        self.cancel_callback: Optional[Callable[[], None]] = None
        tk.Button(
            button_frame,
            text='Cancel',
            bg=COLORS.get('button_bg', PALETTE["bg2"]),
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            command=self._on_cancel
        ).pack(side='right', padx=5)

    def set_cancel_callback(self, callback: Callable[[], None]) -> None:
        self.set_on_cancel(callback)

    def set_on_cancel(self, callback: Callable[[], None]) -> None:
        self.cancel_callback = callback

    def set_status(self, text: str) -> None:
        self.update_status(text)

    def set_progress_text(self, text: str) -> None:
        self.update_progress_info(text)

    def set_progress(self, percentage: float) -> None:
        self.update_progress_bar(percentage)

    def _center_window(self, width: int, height: int) -> None:
        self.window.update_idletasks()
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        x = (sw // 2) - (width // 2)
        y = (sh // 2) - (height // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _create_progress_bar(self) -> None:
        progress_frame = tk.Frame(self.window, bg=COLORS.get('bg_secondary', PALETTE["bg2"]))
        progress_frame.pack(pady=10)

        self.progress_bar_bg = tk.Frame(progress_frame, bg='#555555', height=10, width=300)
        self.progress_bar_bg.pack()

        self.progress_bar_fill = tk.Frame(self.progress_bar_bg, bg=COLORS.get('fg_success', "#1dd1a1"),
                                          height=10, width=1)
        self.progress_bar_fill.place(x=0, y=0)

    def _on_cancel(self) -> None:
        if self.cancel_callback:
            try:
                self.cancel_callback()
            except Exception:
                pass
        self.update_status("🛑 Cancelling...")

    def update_status(self, text: str) -> None:
        if self.window.winfo_exists():
            try:
                self.status_label.config(text=text)
                self.window.update()
            except tk.TclError:
                pass

    def update_progress_info(self, text: str) -> None:
        if self.window.winfo_exists():
            try:
                self.progress_info.config(text=text)
                self.window.update()
            except tk.TclError:
                pass

    def update_progress_bar(self, percentage: float) -> None:
        if self.window.winfo_exists():
            try:
                width = min(int((percentage / 100) * 300), 300)
                self.progress_bar_fill.config(width=width)

                if percentage > 80:
                    self.progress_bar_fill.config(bg='#ff0000')
                elif percentage > 50:
                    self.progress_bar_fill.config(bg=COLORS.get('fg_warning', PALETTE["warning"]))
                else:
                    self.progress_bar_fill.config(bg=COLORS.get('fg_success', "#1dd1a1"))

                self.window.update_idletasks()
            except tk.TclError:
                pass

    def close(self) -> None:
        try:
            self.window.destroy()
        except tk.TclError:
            pass


# ---- Caption Dialog ---------------------------------------------------------

class CaptionDialog:
    """Dialog for displaying and managing captions and hashtags."""

    def __init__(self, parent: tk.Tk, video_title: str, caption: str,
                 hashtags: List[str], save_path: Optional[str] = None) -> None:
        self.parent = parent
        self.video_title = video_title
        self.caption = caption
        self.hashtags = hashtags
        self.save_path = save_path

        self.window = tk.Toplevel(parent)
        try:
            install_style(self.window)
        except Exception:
            pass
        self.window.title(f"Caption & Hashtags - {video_title[:30]}...")
        self.window.geometry("500x400")
        self.window.configure(bg=COLORS.get('bg_primary', PALETTE["bg"]))
        self.window.resizable(False, False)

        self._create_widgets()

    def _create_widgets(self) -> None:
        tk.Label(
            self.window,
            text="Caption",
            fg=COLORS.get('fg_success', "#1dd1a1"),
            bg=COLORS.get('bg_primary', PALETTE["bg"]),
            font=('Segoe UI', 11, 'bold')
        ).pack(pady=(10, 0))

        caption_text = tk.Text(
            self.window, height=3,
            bg=COLORS.get('bg_secondary', PALETTE["bg2"]),
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            wrap='word'
        )
        caption_text.insert('1.0', self.caption)
        caption_text.config(state='disabled')
        caption_text.pack(fill='x', padx=10, pady=5)

        tk.Label(
            self.window,
            text="Hashtags",
            fg=COLORS.get('fg_success', "#1dd1a1"),
            bg=COLORS.get('bg_primary', PALETTE["bg"]),
            font=('Segoe UI', 11, 'bold')
        ).pack(pady=(10, 0))

        hashtag_text = tk.Text(
            self.window, height=5,
            bg=COLORS.get('bg_secondary', PALETTE["bg2"]),
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            wrap='word'
        )
        hashtag_text.insert('1.0', ' '.join(self.hashtags))
        hashtag_text.config(state='disabled')
        hashtag_text.pack(fill='both', expand=True, padx=10, pady=5)

        button_frame = tk.Frame(self.window, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        button_frame.pack(fill='x', pady=10, padx=10)

        tk.Button(
            button_frame,
            text='Copy to Clipboard',
            bg=COLORS.get('button_bg', PALETTE["bg2"]),
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            command=self._copy_to_clipboard
        ).pack(side='left', padx=5)

        tk.Button(
            button_frame,
            text='Save to File',
            bg=COLORS.get('button_bg', PALETTE["bg2"]),
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            command=self._save_to_file
        ).pack(side='left', padx=5)

        tk.Button(
            button_frame,
            text='Close',
            bg='#666666',
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            command=self.window.destroy
        ).pack(side='right', padx=5)

    def _copy_to_clipboard(self) -> None:
        text_to_copy = f"{self.caption}\n{' '.join(self.hashtags)}"
        self.window.clipboard_clear()
        self.window.clipboard_append(text_to_copy)
        try:
            show_toast(self.window, "Copied ✓")
        except Exception:
            pass
        messagebox.showinfo("Copied", "Caption and hashtags copied to clipboard!")

    def _save_to_file(self) -> None:
        try:
            directory = self.save_path
            if directory is None:
                directory = filedialog.askdirectory(title="Choose a folder to save")
                if not directory:
                    return
            base = self._safe_filename(self.video_title[:20])
            file_path = f"{directory}/{base}_caption.txt"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"{self.caption}\n{' '.join(self.hashtags)}")

            messagebox.showinfo('Saved', f'Saved to:\n{file_path}')
        except Exception as e:
            messagebox.showerror('Save Error', f'Could not save file:\n{e}')

    def _safe_filename(self, text: str) -> str:
        safe = [c if c.isalnum() or c in (' ', '-', '_') else '_' for c in text]
        return (''.join(safe).strip() or 'caption')


# ---- Prompt Builder (Panel) -------------------------------------------------

_DEFAULT_PRESETS = [
    {
        "name": "Research & Insight (Expert Analysis)",
        "template": (
            "You are a senior domain expert. Using the transcript below, produce: "
            "1) 10 key insights for {audience}, 2) frameworks/models mentioned or implied, "
            "3) contradictions/assumptions, 4) a {plan_horizon}-day action plan prioritized by impact vs effort, "
            "5) risks & counterarguments.\n\n"
            "Constraints: tone={tone}, max_length={target_length}, reading_level={reading_level}.\n\n"
            "Transcript:\n[Transcript here]\n\n"
            "Return clean sections with headers and bullets. If data is missing, list exact questions to ask next."
        ),
        "controls": [
            {"id": "audience", "label": "Audience", "type": "select",
             "options": ["Beginner", "Intermediate", "Advanced"], "default": "Beginner"},
            {"id": "plan_horizon", "label": "Plan Horizon (days)", "type": "integer", "default": 30, "min": 1, "max": 365},
            {"id": "tone", "label": "Tone", "type": "select",
             "options": ["Direct", "Neutral", "Friendly"], "default": "Direct"},
            {"id": "target_length", "label": "Target Length", "type": "select",
             "options": ["Short", "Medium", "Long"], "default": "Medium"},
            {"id": "reading_level", "label": "Reading Level", "type": "select",
             "options": ["Middle School", "High School", "College"], "default": "High School"},
        ],
    },
    {
        "name": "Action Plan (90-Day)",
        "template": (
            "Turn this transcript into a {days}-day plan with milestones → tasks → owners → deadlines. "
            "Include effort (S/M/L) and impact (1–5).\n\nTranscript:\n[Transcript here]\n\n"
            "Return as a clean checklist and a CSV-ready table."
        ),
        "controls": [{"id": "days", "label": "Days", "type": "integer", "default": 90, "min": 7, "max": 365}],
    },
    {
        "name": "Persona Rewrite",
        "template": (
            "Rewrite the key takeaways for a {persona} audience in ~{length} words. Replace jargon with their vocabulary. "
            "End with a single, specific CTA.\n\nTranscript:\n[Transcript here]"
        ),
        "controls": [
            {"id": "persona", "label": "Persona", "type": "select",
             "options": ["Founder", "Engineer", "Marketer", "Investor"], "default": "Founder"},
            {"id": "length", "label": "Length (words)", "type": "integer", "default": 150, "min": 50, "max": 400},
        ],
    },
    {
        "name": "Score & Improve",
        "template": (
            "Rate this transcript on a 1–100 scale across: clarity, evidence, actionability, originality, brand-safety."
            "{weight_actionability}\n\nTranscript:\n[Transcript here]\n\n"
            "Output sections: Scores, Flaws, Fix Plan (with bullets ordered by ROI)."
        ),
        "controls": [
            {"id": "weight_actionability", "label": "Weight Actionability", "type": "checkbox",
             "default": True, "on": " Emphasize actionability.", "off": ""},
        ],
    },
    {
        "name": "Viral Clip Extractor (Hooks)",
        "template": (
            "From the transcript, list {n_hooks} timestamped hook moments for {platforms}. "
            "For each: a 2-word hook phrase, 1-sentence angle, and brand-safety flags to avoid.\n\n"
            "Transcript:\n[Transcript here]\n\n"
            "Return a compact table. Prioritize concrete numbers, contrarian claims, and emotion triggers."
        ),
        "controls": [
            {"id": "n_hooks", "label": "# of hooks", "type": "slider", "min": 3, "max": 12, "default": 8},
            {"id": "platforms", "label": "Platforms", "type": "multiselect",
             "options": ["TikTok", "Reels", "Shorts", "LinkedIn"], "default": ["TikTok", "Reels", "Shorts"]},
        ],
    },
]


def _load_presets_from_json() -> List[Dict[str, Any]]:
    """Load presets from prompts.json if present; otherwise fall back to built-ins."""
    for candidate in [getattr(Path('.'), 'cwd', Path('.'))(), Path(__file__).parent, Path.cwd()]:
        json_path = candidate / "prompts.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        return data
            except Exception:
                pass
    try:
        from config import PROMPTS_FILE  # type: ignore
        p = Path(PROMPTS_FILE)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
    except Exception:
        pass
    return _DEFAULT_PRESETS


class PromptBuilderPanel(tk.Frame):
    """Preset-driven prompt builder with live preview and copy actions."""

    def __init__(self, parent: tk.Widget, transcript_provider: Callable[[], str]) -> None:
        super().__init__(parent, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        install_style(self)

        self.transcript_provider = transcript_provider
        self.presets = _load_presets_from_json()

        # Header + preset selector
        header = tk.Frame(self, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        header.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(
            header, text="Prompt Builder", font=("Segoe UI Semibold", 11),
            bg=COLORS.get('bg_primary', PALETTE["bg"]), fg=COLORS.get('fg_primary', PALETTE["text"])
        ).pack(side="left")

        self.preset_var = tk.StringVar(value=self.presets[0]["name"] if self.presets else "")
        self.preset_cb = ttk.Combobox(
            self, textvariable=self.preset_var, values=[p["name"] for p in self.presets],
            state="readonly", width=36, style="Dark.TCombobox"
        )
        self.preset_cb.pack(fill="x", padx=8)
        self.preset_cb.bind("<<ComboboxSelected>>", lambda _e: self._render_controls())

        # Dynamic controls
        self.controls_frame = tk.Frame(self, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        self.controls_frame.pack(fill="x", padx=8, pady=6)

        # Preview
        tk.Label(
            self, text="Preview", font=("Segoe UI", 10, "bold"),
            bg=COLORS.get('bg_primary', PALETTE["bg"]), fg=COLORS.get('fg_primary', PALETTE["text"])
        ).pack(anchor="w", padx=8)

        self.preview = tk.Text(self, height=12)
        style_text_widget(self.preview)
        self.preview.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.preview.config(state="disabled")

        # Buttons
        btns = tk.Frame(self, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="Copy Prompt", style="Ghost.TButton", command=self.copy_prompt).pack(side="left", padx=4)
        ttk.Button(btns, text="Copy + Transcript", style="Accent.TButton",
                   command=self.copy_prompt_with_transcript).pack(side="right", padx=4)

        self._vars: Dict[str, Any] = {}
        self._render_controls()

    def _current_preset(self) -> Dict[str, Any]:
        name = self.preset_var.get()
        for p in self.presets:
            if p.get("name") == name:
                return p
        return self.presets[0] if self.presets else {"name": "Prompt", "template": "", "controls": []}

    def _render_controls(self) -> None:
        for w in list(self.controls_frame.children.values()):
            w.destroy()
        self._vars.clear()

        preset = self._current_preset()
        for ctl in preset.get("controls", []):
            cid = ctl.get("id")
            label = ctl.get("label", cid)
            ctype = (ctl.get("type") or "text").lower()

            row = tk.Frame(self.controls_frame, bg=COLORS.get('bg_primary', PALETTE["bg"]))
            row.pack(fill="x", pady=3)

            tk.Label(row, text=label, bg=COLORS.get('bg_primary', PALETTE["bg"]),
                     fg=COLORS.get('fg_primary', PALETTE["text"])).pack(side="left")

            if ctype == "text":
                var = tk.StringVar(value=str(ctl.get("default", "")))
                ent = ttk.Entry(row, textvariable=var, width=30, style="Dark.TEntry")
                ent.pack(side="right", fill="x", expand=True)
                ent.bind("<KeyRelease>", lambda _e: self._refresh_preview())

            elif ctype == "integer":
                var = tk.IntVar(value=int(ctl.get("default", 0)))
                ent = ttk.Entry(row, textvariable=var, width=12, style="Dark.TEntry")
                ent.pack(side="right")
                ent.bind("<KeyRelease>", lambda _e: self._refresh_preview())

            elif ctype == "select":
                var = tk.StringVar(value=str(ctl.get("default", "")))
                cb = ttk.Combobox(row, textvariable=var, values=ctl.get("options", []),
                                  state="readonly", width=24, style="Dark.TCombobox")
                cb.pack(side="right")
                cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_preview())

            elif ctype == "multiselect":
                opts = ctl.get("options", [])
                defaults = ctl.get("default", [])
                var = {opt: tk.BooleanVar(value=(opt in defaults)) for opt in opts}
                btn = ttk.Menubutton(row, text="Select…", width=12, style="Ghost.TButton")
                menu = tk.Menu(btn, tearoff=False, background=PALETTE["bg2"], foreground=PALETTE["text"],
                               activebackground=PALETTE["accent"], activeforeground="white")
                btn["menu"] = menu
                for opt in opts:
                    menu.add_checkbutton(label=opt, variable=var[opt],
                                         command=self._refresh_preview)
                btn.pack(side="right")

            elif ctype == "checkbox":
                var = tk.BooleanVar(value=bool(ctl.get("default", False)))
                chk = ttk.Checkbutton(row, variable=var, text="")
                chk.pack(side="right")
                chk.configure(command=self._refresh_preview)

            elif ctype == "slider":
                vmin = int(ctl.get("min", 0))
                vmax = int(ctl.get("max", 10))
                var = tk.IntVar(value=int(ctl.get("default", vmin)))
                sc = ttk.Scale(row, from_=vmin, to=vmax, orient="horizontal", variable=var,
                               command=lambda _v: self._refresh_preview())
                sc.pack(side="right", fill="x", expand=True)

            else:
                var = tk.StringVar(value=str(ctl.get("default", "")))
                ent = ttk.Entry(row, textvariable=var, width=30, style="Dark.TEntry")
                ent.pack(side="right", fill="x", expand=True)
                ent.bind("<KeyRelease>", lambda _e: self._refresh_preview())

            self._vars[cid] = (ctype, var, ctl)

        self._refresh_preview()

    def _collect_values(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for cid, (ctype, var, ctl) in self._vars.items():
            if ctype == "multiselect":
                selected = [k for k, v in var.items() if v.get()]
                values[cid] = ", ".join(selected) if selected else ""
            elif ctype == "checkbox":
                on = ctl.get("on", "")
                off = ctl.get("off", "")
                values[cid] = on if bool(var.get()) else off
            else:
                values[cid] = var.get()
        return values

    def _format_template(self, template: str, values: Dict[str, Any]) -> str:
        def repl(m):
            key = m.group(1)
            return str(values.get(key, m.group(0)))
        return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, template)

    def _refresh_preview(self) -> None:
        preset = self._current_preset()
        values = self._collect_values()
        prompt = self._format_template(preset.get("template", ""), values)
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", prompt)
        self.preview.config(state="disabled")

    def _get_prompt_text(self, include_transcript: bool) -> str:
        preset = self._current_preset()
        values = self._collect_values()
        base = self._format_template(preset.get("template", ""), values)
        if include_transcript:
            return base.replace("[Transcript here]", self.transcript_provider())
        return base

    def copy_prompt(self) -> None:
        txt = self._get_prompt_text(include_transcript=False)
        self.clipboard_clear()
        self.clipboard_append(txt)
        show_toast(self, "Prompt copied ✓")

    def copy_prompt_with_transcript(self) -> None:
        txt = self._get_prompt_text(include_transcript=True)
        self.clipboard_clear()
        self.clipboard_append(txt)
        show_toast(self, "Prompt + transcript copied ✓")


# ---- Transcript Dialog ------------------------------------------------------

class TranscriptDialog:
    """Dialog for displaying video transcripts (with Prompt Builder side-panel)."""

    def __init__(self, parent: tk.Tk, title: str, video_id: str, transcript: str) -> None:
        self.parent = parent
        self.title = title
        self.video_id = video_id
        self.transcript = transcript

        self.window = tk.Toplevel(parent)
        try:
            install_style(self.window)
        except Exception:
            pass
        self.window.title(f"Transcript - {title[:50]}...")
        self.window.geometry("1024x640")
        self.window.configure(bg=COLORS.get('bg_primary', PALETTE["bg"]))

        self._create_widgets()

    def _create_widgets(self) -> None:
        header = tk.Frame(self.window, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        header.pack(fill='x', padx=10, pady=10)

        tk.Label(
            header,
            text=f"Title: {self.title}",
            fg=COLORS.get('fg_accent', PALETTE["accent"]),
            bg=COLORS.get('bg_primary', PALETTE["bg"]),
            font=('Segoe UI', 12, 'bold')
        ).pack(anchor='w')

        tk.Label(
            header,
            text=f"Video ID: {self.video_id}",
            fg='#888888',
            bg=COLORS.get('bg_primary', PALETTE["bg"]),
            font=('Segoe UI', 10)
        ).pack(anchor='w')

        # Body uses GRID: left expands, right fixed width
        body = tk.Frame(self.window, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: transcript
        text_card = tk.Frame(body, bg=PALETTE["card"], bd=1, relief="solid")
        text_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.text_widget = tk.Text(
            text_card,
            bg=COLORS.get('bg_secondary', PALETTE["bg2"]),
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            font=('Consolas', 11),
            wrap='word',
            selectbackground='#444444',
            selectforeground=COLORS.get('fg_primary', PALETTE["text"]),
            insertbackground=COLORS.get('fg_primary', PALETTE["text"])
        )
        style_text_widget(self.text_widget)

        scrollbar = tk.Scrollbar(text_card, orient='vertical', command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.text_widget.insert('1.0', self.transcript)
        self.text_widget.config(state='disabled')

        # Right: prompt builder (fixed width)
        def _get_transcript() -> str:
            return self.transcript

        builder_container = tk.Frame(body, width=360, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        builder_container.grid(row=0, column=1, sticky='ns')
        builder_container.grid_propagate(False)

        try:
            self.builder = PromptBuilderPanel(builder_container, transcript_provider=_get_transcript)
            self.builder.pack(fill="both", expand=True)
        except Exception as e:
            err = tk.Label(builder_container, text=f"Prompt Builder failed:\n{e}",
                           bg=COLORS.get('bg_primary', PALETTE["bg"]),
                           fg=PALETTE["warning"], justify="left")
            err.pack(fill="both", expand=True, padx=8, pady=8)

        # Bottom buttons (for transcript)
        buttons = tk.Frame(self.window, bg=COLORS.get('bg_primary', PALETTE["bg"]))
        buttons.pack(fill='x', pady=5, padx=10)

        ttk.Button(buttons, text='Copy to Clipboard', style="Ghost.TButton",
                   command=self._copy).pack(side='left', padx=5)
        ttk.Button(buttons, text='Save to File', style="Ghost.TButton",
                   command=self._save).pack(side='left', padx=5)
        ttk.Button(buttons, text='Close', style="Accent.TButton",
                   command=self.window.destroy).pack(side='right', padx=5)

    def _copy(self) -> None:
        self.window.clipboard_clear()
        self.window.clipboard_append(self.transcript)
        try:
            show_toast(self.window, "Copied ✓")
        except Exception:
            pass
        messagebox.showinfo("Copied", "Transcript copied to clipboard!")

    def _save(self) -> None:
        try:
            from config import AUDIO_CLIPS_PATH  # type: ignore
            AUDIO_CLIPS_PATH.mkdir(exist_ok=True)
            path = AUDIO_CLIPS_PATH / f"{self.video_id}_transcript.txt"
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"Title: {self.title}\n")
                f.write(f"Video ID: {self.video_id}\n")
                f.write("=" * 50 + "\n\n")
                f.write(self.transcript)
            messagebox.showinfo("Saved", f"Transcript saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save transcript:\n{e}")


# ---- Manual Transcript Dialog -----------------------------------------------

class ManualTranscriptDialog:
    """Dialog for adding a transcript manually."""

    def __init__(self, parent: tk.Tk, winners_manager) -> None:
        self.parent = parent
        self.winners_manager = winners_manager
        self.result = None

        self.window = tk.Toplevel(parent)
        self.window.title("Add Manual Transcript")
        self.window.geometry("600x700")
        install_style(self.window)
        self.window.transient(parent)
        self.window.grab_set()

        self._create_widgets()
        self.window.wait_window()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=15)
        main_frame.pack(fill="both", expand=True)

        # Title
        ttk.Label(main_frame, text="Title:", style="Section.TLabel").pack(anchor="w")
        self.title_var = tk.StringVar()
        title_entry = ttk.Entry(main_frame, textvariable=self.title_var)
        title_entry.pack(fill="x", pady=(2, 10))
        self.title_var.trace_add("write", self._check_inputs)

        # Folder
        ttk.Label(main_frame, text="Folder:", style="Section.TLabel").pack(anchor="w")
        self.folder_var = tk.StringVar()
        folders = self.winners_manager.get_all_folders()
        folder_combo = ttk.Combobox(main_frame, textvariable=self.folder_var, values=folders, state="readonly")
        if folders:
            folder_combo.set(folders[0])
        folder_combo.pack(fill="x", pady=(2, 10))

        # Tags
        ttk.Label(main_frame, text="Tags (comma-separated):", style="Section.TLabel").pack(anchor="w")
        self.tags_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.tags_var).pack(fill="x", pady=(2, 10))

        # Notes
        ttk.Label(main_frame, text="Notes:", style="Section.TLabel").pack(anchor="w")
        self.notes_text = tk.Text(main_frame, height=4)
        style_text_widget(self.notes_text)
        self.notes_text.pack(fill="x", pady=(2, 10))

        # Transcript Text
        ttk.Label(main_frame, text="Transcript Text:", style="Section.TLabel").pack(anchor="w")
        self.transcript_text = tk.Text(main_frame, height=15)
        style_text_widget(self.transcript_text)
        self.transcript_text.pack(fill="both", expand=True, pady=(2, 10))
        self.transcript_text.bind("<KeyRelease>", self._check_inputs)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        self.save_button = ttk.Button(button_frame, text="Save", command=self._on_save, state="disabled")
        self.save_button.pack(side="right", padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side="right")

    def _check_inputs(self, *args):
        title_ok = self.title_var.get().strip() != ""
        text_ok = self.transcript_text.get("1.0", "end-1c").strip() != ""
        self.save_button.config(state="normal" if title_ok and text_ok else "disabled")

    def _on_save(self):
        self.result = {
            "title": self.title_var.get().strip(),
            "folder": self.folder_var.get(),
            "tags": [tag.strip() for tag in self.tags_var.get().split(",") if tag.strip()],
            "notes": self.notes_text.get("1.0", "end-1c").strip(),
            "text": self.transcript_text.get("1.0", "end-1c").strip(),
        }
        self.window.destroy()


# ---- Folder Manager Dialog --------------------------------------------------

class FolderManagerDialog:
    """Dialog for managing folders."""

    def __init__(self, parent: tk.Tk, winners_manager) -> None:
        self.parent = parent
        self.wm = winners_manager

        self.window = tk.Toplevel(parent)
        self.window.title("Manage Folders")
        self.window.geometry("400x500")
        install_style(self.window)
        self.window.transient(parent)
        self.window.grab_set()

        self._create_widgets()
        self.window.wait_window()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=15)
        main_frame.pack(fill="both", expand=True)

        # Folder List
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(list_frame, selectmode="single")
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        self.rename_button = ttk.Button(button_frame, text="Rename", command=self._rename_folder, state="disabled")
        self.rename_button.pack(side="left")

        self.delete_button = ttk.Button(button_frame, text="Delete", command=self._delete_folder, state="disabled")
        self.delete_button.pack(side="left", padx=5)

        ttk.Button(button_frame, text="Add New", command=self._add_folder).pack(side="left")
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side="right")

        self._populate_folders()

    def _populate_folders(self):
        self.listbox.delete(0, "end")
        for folder in self.wm.get_all_folders():
            self.listbox.insert("end", folder)
        self._on_select()

    def _on_select(self, event=None):
        is_selected = bool(self.listbox.curselection())
        is_default = False
        if is_selected:
            selected_folder = self.listbox.get(self.listbox.curselection())
            is_default = selected_folder == "Default"

        self.rename_button.config(state="normal" if is_selected and not is_default else "disabled")
        self.delete_button.config(state="normal" if is_selected and not is_default else "disabled")

    def _add_folder(self):
        new_name = simpledialog.askstring("New Folder", "Enter new folder name:", parent=self.window)
        if new_name and new_name.strip():
            if self.wm.add_folder(new_name.strip()):
                self._populate_folders()
            else:
                messagebox.showerror("Error", "Folder already exists or is invalid.", parent=self.window)

    def _rename_folder(self):
        selection = self.listbox.curselection()
        if not selection: return

        old_name = self.listbox.get(selection[0])
        new_name = simpledialog.askstring("Rename Folder", f"Enter new name for '{old_name}':", parent=self.window)

        if new_name and new_name.strip():
            if self.wm.rename_folder(old_name, new_name.strip()):
                self._populate_folders()
            else:
                messagebox.showerror("Error", "New folder name is invalid or already exists.", parent=self.window)

    def _delete_folder(self):
        selection = self.listbox.curselection()
        if not selection: return

        folder_name = self.listbox.get(selection[0])
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete the folder '{folder_name}'?\n"
            "All items inside will be moved to the 'Default' folder.",
            parent=self.window
        )
        if confirm:
            if self.wm.remove_folder(folder_name):
                self._populate_folders()
            else:
                messagebox.showerror("Error", "Could not delete folder.", parent=self.window)


# ---- Treeview Sort ----------------------------------------------------------

def sort_treeview_column(tree: ttk.Treeview, col: str, reverse: bool = False) -> None:
    """
    Sort a ttk.Treeview by a given column.
    Handles numeric values (including percentages), times (HH:MM:SS), and strings.
    """
    try:
        items = []
        for child in tree.get_children(''):
            cell = tree.set(child, col)
            items.append((cell, child))

        def parse_time_to_seconds(s: str) -> float:
            parts = s.split(':')
            if len(parts) == 3:
                h, m, sec = parts
                return int(h) * 3600 + int(m) * 60 + float(sec)
            if len(parts) == 2:
                m, sec = parts
                return int(m) * 60 + float(sec)
            return float(s)

        def numeric_key(item):
            val = str(item[0]).strip()
            if val.endswith('%'):
                try:
                    return float(val.rstrip('%'))
                except ValueError:
                    return float('inf')
            if ':' in val:
                try:
                    return parse_time_to_seconds(val)
                except Exception:
                    pass
            cleaned = val.replace(',', '').replace('$', '')
            try:
                return float(cleaned)
            except ValueError:
                return float('inf')

        try:
            sample = next(v for v, _ in items if str(v).strip() != "")
            _ = numeric_key((sample, None))
            items.sort(key=numeric_key, reverse=reverse)
        except (ValueError, StopIteration):
            items.sort(key=lambda x: str(x[0]).lower(), reverse=reverse)
        except Exception:
            items.sort(key=lambda x: str(x[0]).lower(), reverse=reverse)

        for index, (_val, iid) in enumerate(items):
            tree.move(iid, '', index)

        for column in tree["columns"]:
            heading = tree.heading(column)
            text = heading.get("text", column)
            text = (text or column).replace(' ↑', '').replace(' ↓', '')
            if column == col:
                text = f"{text} {'↓' if reverse else '↑'}"
            tree.heading(column, text=text)

    except Exception as e:
        print(f"[TreeSort] error sorting '{col}': {e}")


# ---- Timer Widget -----------------------------------------------------------

class TimerWidget:
    """Timer widget for countdown displays."""

    def __init__(self, parent: tk.Widget) -> None:
        self.parent = parent
        self.end_time = None
        self.timer_job = None

        self.timer_label = tk.Label(
            parent,
            text='🕒 Time Left to Hustle: --:--:--',
            fg=COLORS.get('fg_primary', PALETTE["text"]),
            bg=COLORS.get('bg_primary', PALETTE["bg"]),
            font=('Segoe UI', 11, 'bold')
        )

    def pack(self, **kwargs) -> None:
        self.timer_label.pack(**kwargs)

    def place(self, **kwargs) -> None:
        self.timer_label.place(**kwargs)

    def grid(self, **kwargs) -> None:
        self.timer_label.grid(**kwargs)

    def start_timer(self, end_time) -> None:
        """Start countdown until the given datetime."""
        self.end_time = end_time
        self._update_display()

    def _update_display(self) -> None:
        if self.end_time is None:
            return

        from datetime import datetime
        remaining = self.end_time - datetime.now()

        if remaining.total_seconds() <= 0:
            self.timer_label.config(
                text='⛔ Hustle Time Over!',
                fg=COLORS.get('fg_warning', PALETTE["warning"])
            )
            return

        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours == 0 and minutes < 5:
            self.timer_label.config(
                text=f'⏳ Time Left to Hustle: {hours:02d}:{minutes:02d}:{seconds:02d}',
                fg=COLORS.get('fg_warning', PALETTE["warning"])
            )
        else:
            self.timer_label.config(
                text=f'🕒 Time Left to Hustle: {hours:02d}:{minutes:02d}:{seconds:02d}',
                fg=COLORS.get('fg_primary', PALETTE["text"])
            )

        self.timer_job = self.parent.after(1000, self._update_display)

    def stop_timer(self) -> None:
        if self.timer_job:
            self.parent.after_cancel(self.timer_job)
            self.timer_job = None


class FacebookErrorDialog(tk.Toplevel):
    def __init__(self, parent, url: str, on_retry_cookies: callable, on_update_module: callable):
        super().__init__(parent)
        self.title("Facebook Extraction Failed")
        self.geometry("500x250")
        try:
            install_style(self)
        except Exception:
            self.configure(bg=PALETTE['bg'])

        self.transient(parent)
        self.grab_set()

        self.url = url
        self.on_retry_cookies = on_retry_cookies
        self.on_update_module = on_update_module

        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Facebook Extraction Is Unstable", font=("Segoe UI", 12, "bold")).pack(pady=5)

        body_text = "We tried several methods but could not get the video data. This can happen if the video is private, requires a login, or if Facebook changed their API.\n\nYou can try the following options:"
        ttk.Label(main_frame, text=body_text, wraplength=450).pack(pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=15)

        ttk.Button(button_frame, text="Retry with Browser Cookies", command=self._retry_with_cookies).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Update Module to Master", command=self._update_module).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Open in Browser", command=self._open_in_browser).pack(side='left', padx=5)

    def _retry_with_cookies(self):
        self.on_retry_cookies()
        self.destroy()

    def _update_module(self):
        self.on_update_module()
        self.destroy()

    def _open_in_browser(self):
        import webbrowser
        webbrowser.open(self.url)
        self.destroy()
