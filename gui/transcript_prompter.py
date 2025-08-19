# gui/transcript_prompter.py
# ---------------------------------------------------------------------
# DO NOT RENAME THIS MODULE.
# Backwards-compatible Transcript window WITH the new Prompt Builder.
# Whatever the caller imported before (functions/classes below) will
# now open the upgraded UI.
# ---------------------------------------------------------------------

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Callable
import datetime

import tkinter as tk
from tkinter import ttk, messagebox

# Re-use existing styling/helpers (these exist in your project)
try:
    from gui.components import install_style, style_text_widget, show_toast
    from data.transcripts_manager import TranscriptsManager
    from data.winners_manager import WinnersManager
except Exception:
    # Very safe fallbacks so this file never hard-crashes if helpers move.
    def install_style(_root: tk.Misc) -> None:
        style = ttk.Style(_root)
        try:
            _root.tk.call("tk", "scaling", 1.2)
        except Exception:
            pass
        style.theme_use(style.theme_use() or "default")
        style.configure("Card.TFrame", background="#1a1d24")
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", foreground="#8892a0")
        style.configure("Accent.TButton")

    def style_text_widget(w: tk.Text) -> None:
        w.configure(
            bg="#0f1115",
            fg="#e6edf3",
            insertbackground="#e6edf3",
            highlightthickness=0,
            relief="flat",
            padx=10,
            pady=8,
            font=("Consolas", 10),
            wrap="word",
        )

    def show_toast(parent: tk.Misc, text: str) -> None:
        try:
            parent.bell()
        except Exception:
            pass
        messagebox.showinfo("Copied", text, parent=parent if isinstance(parent, tk.Tk) or isinstance(parent, tk.Toplevel) else None)


# ---------- prompts.json loader ----------------------------------------------

def _project_root() -> Path:
    here = Path(__file__).resolve()
    root = here.parent.parent
    return root if (root / "prompts.json").exists() else Path.cwd()


def _load_prompts_json() -> List[Dict[str, Any]]:
    paths = [
        _project_root() / "prompts.json",                 # repo root
        Path(__file__).resolve().parent / "prompts.json", # same folder
    ]
    for p in paths:
        try:
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            continue

    # Fallback default (so UI still works if file missing)
    return [{
        "id": "research_expert",
        "name": "Research & Insight (Expert Analysis)",
        "template": (
            "You are a senior domain expert. Using the transcript below, produce: "
            "1) 10 key insights for {audience}, 2) frameworks/models, "
            "3) contradictions/assumptions, 4) a {horizon}-day action plan prioritized by impact vs effort, "
            "5) risks & counterarguments.\n\n"
            "Constraints: tone={tone}, max length={length}, reading level={reading_level}.\n\n"
            "Transcript:\n{transcript}\n\n"
            "Return clean sections with headers and bullets."
        ),
        "fields": [
            {"key": "audience", "label": "Audience", "type": "select",
             "options": ["Beginner", "Intermediate", "Advanced"], "default": "Beginner"},
            {"key": "horizon", "label": "Plan Horizon (days)", "type": "number", "default": 30},
            {"key": "tone", "label": "Tone", "type": "select",
             "options": ["Direct", "Friendly", "Formal"], "default": "Direct"},
            {"key": "length", "label": "Target Length", "type": "select",
             "options": ["Short", "Medium", "Long"], "default": "Medium"},
            {"key": "reading_level", "label": "Reading Level", "type": "select",
             "options": ["Middle School", "High School", "College"], "default": "High School"},
        ]
    }]


# ---------- Dynamic field row -------------------------------------------------

class _FieldRow:
    def __init__(self, frame: ttk.Frame, spec: Dict[str, Any]) -> None:
        self.spec = spec
        self.key = str(spec.get("key") or spec.get("id") or spec.get("label") or "param")
        self.get_value: Callable[[], Any]
        self._build(frame)

    def _build(self, frame: ttk.Frame) -> None:
        label = ttk.Label(frame, text=str(self.spec.get("label", self.key)))
        label.pack(anchor="w", pady=(4, 0))

        ftype = (self.spec.get("type") or "text").lower()
        default = self.spec.get("default")

        if ftype in ("select", "dropdown", "combo"):
            values = list(self.spec.get("options", []))
            var = tk.StringVar(value=str(default if default is not None else (values[0] if values else "")))
            cb = ttk.Combobox(frame, values=values, textvariable=var, state="readonly")
            cb.pack(fill="x", pady=2)
            self.get_value = lambda v=var: v.get()

        elif ftype in ("number", "int", "float"):
            var = tk.StringVar(value=str(default if default is not None else "0"))
            ent = ttk.Entry(frame, textvariable=var)
            ent.pack(fill="x", pady=2)

            def _coerce():
                s = var.get().strip()
                try:
                    return int(s)
                except ValueError:
                    try:
                        return float(s)
                    except ValueError:
                        return s

            self.get_value = _coerce

        elif ftype in ("checkbox", "toggle", "bool"):
            var = tk.BooleanVar(value=bool(default))
            chk = ttk.Checkbutton(frame, text=str(self.spec.get("text", "Enabled")), variable=var)
            chk.pack(anchor="w", pady=2)
            self.get_value = lambda v=var: bool(v.get())

        elif ftype == "slider":
            minv = float(self.spec.get("min", 0))
            maxv = float(self.spec.get("max", 10))
            step = float(self.spec.get("step", 1))
            init = float(default if default is not None else minv)
            var = tk.DoubleVar(value=init)

            row = ttk.Frame(frame)
            row.pack(fill="x")
            val_lbl = ttk.Label(row, text=f"{init:g}")
            val_lbl.pack(side="right", padx=4)

            def _on_slide(_ev=None):
                v = round(var.get() / step) * step
                var.set(v)
                val_lbl.config(text=f"{v:g}")

            scale = ttk.Scale(row, from_=minv, to=maxv, orient="horizontal", variable=var, command=_on_slide)
            scale.pack(side="left", fill="x", expand=True)
            self.get_value = lambda v=var: round(v.get() / step) * step

        elif ftype in ("multiselect", "checklist"):
            options = list(self.spec.get("options", []))
            vars_: List[tk.BooleanVar] = []
            for opt in options:
                v = tk.BooleanVar(value=(opt in (default or [])))
                cb = ttk.Checkbutton(frame, text=str(opt), variable=v)
                cb.pack(anchor="w")
                vars_.append(v)
            self.get_value = lambda vs=vars_, opts=options: [o for o, sv in zip(opts, vs) if sv.get()]

        else:  # text
            var = tk.StringVar(value=str(default if default is not None else ""))
            ent = ttk.Entry(frame, textvariable=var)
            ent.pack(fill="x", pady=2)
            self.get_value = lambda v=var: v.get()


# ---------- Main window -------------------------------------------------------

class TranscriptDialog:
    """
    Backwards-compatible transcript window that also hosts the Prompt Builder.
    Keep constructor signature minimal: (parent, title, video_id, transcript)
    """

    def __init__(self, parent: tk.Tk, video_title: str, video_id: str, transcript: str, on_save_callback: Callable[[], None] = None) -> None:
        self.parent = parent
        self.video_title = video_title
        self.video_id = video_id
        self.transcript = transcript
        self.on_save_callback = on_save_callback

        self.prompts: List[Dict[str, Any]] = _load_prompts_json()

        self.win = tk.Toplevel(parent)
        self.win.title(f"Transcript - {video_title}…")
        self.win.geometry("1180x720")
        self.win.minsize(980, 600)
        self.win.configure(bg="#0f1115")
        install_style(self.win)

        # Layout: two columns
        self._build_left()
        self._build_right()

        # Status / bottom buttons (Copy + Close)
        bottom = ttk.Frame(self.win)
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 10))

        left_buttons = ttk.Frame(bottom)
        left_buttons.pack(side="left")

        ttk.Button(left_buttons, text="Copy Transcript", command=self._copy_transcript).pack(side="left", padx=(0, 5))

        self.save_button = ttk.Button(left_buttons, text="Save Transcript", command=self._save_transcript)
        self.save_button.pack(side="left")

        if not self.video_id:
            self.save_button.config(state="disabled")
            # You might want a tooltip here to explain why it's disabled.
            # from gui.components import Tooltip
            # Tooltip(self.save_button, "Video ID is missing, cannot save.")

        ttk.Button(bottom, text="Close", command=self.win.destroy).pack(side="right")

        # bring to front
        self.win.transient(parent)
        self.win.lift()
        try:
            self.win.attributes("-topmost", True)
            self.win.after(150, lambda: self.win.attributes("-topmost", False))
        except Exception:
            pass

    # ----- left column: transcript -------------------------------------------

    def _build_left(self) -> None:
        left = ttk.Frame(self.win)
        left.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)

        meta = ttk.Frame(left)
        meta.pack(fill="x", pady=(0, 6))
        ttk.Label(meta, text=f"Title: {self.video_title}", style="Section.TLabel").pack(anchor="w")
        ttk.Label(meta, text=f"Video ID: {self.video_id}", style="Muted.TLabel").pack(anchor="w")

        card = ttk.Frame(left, style="Card.TFrame", padding=2)
        card.pack(fill="both", expand=True)

        self.txt = tk.Text(card, wrap="word")
        style_text_widget(self.txt)
        y = ttk.Scrollbar(card, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=y.set)
        self.txt.pack(side="left", fill="both", expand=True)
        y.pack(side="right", fill="y")

        self.txt.insert("1.0", self.transcript)
        self.txt.configure(state="disabled")

    # ----- right column: prompt builder --------------------------------------

    def _build_right(self) -> None:
        right = ttk.Frame(self.win, width=420)
        right.pack(side="right", fill="y", padx=(6, 12), pady=12)

        card = ttk.Frame(right, style="Card.TFrame", padding=10)
        card.pack(fill="both", expand=True)

        ttk.Label(card, text="Prompt Builder", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

        # Preset selector
        ttk.Label(card, text="Preset").pack(anchor="w")
        self.preset_names = [str(p.get("name") or p.get("id")) for p in self.prompts]
        self.preset_var = tk.StringVar(value=self.preset_names[0] if self.preset_names else "Preset")
        self.preset_cb = ttk.Combobox(card, values=self.preset_names, textvariable=self.preset_var, state="readonly")
        self.preset_cb.pack(fill="x", pady=(0, 8))
        self.preset_cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        # dynamic fields
        self.fields_frame = ttk.Frame(card)
        self.fields_frame.pack(fill="x", pady=(0, 8))

        # preview
        ttk.Label(card, text="Preview").pack(anchor="w")
        self.preview = tk.Text(card, height=10, wrap="word")
        style_text_widget(self.preview)
        self.preview.configure(state="disabled")
        self.preview.pack(fill="both", expand=True, pady=(2, 8))

        # buttons
        buttons = ttk.Frame(card)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Copy Prompt", style="Accent.TButton", command=self._copy_prompt).pack(side="left")
        ttk.Button(buttons, text="Copy + Transcript", command=self._copy_prompt_with_transcript).pack(side="right")

        # initial render
        self._render_fields()
        self._refresh_preview()

    def _current_preset(self) -> Dict[str, Any]:
        name = self.preset_var.get()
        for p in self.prompts:
            if (p.get("name") or p.get("id")) == name:
                return p
        return self.prompts[0]

    def _clear_fields(self) -> None:
        for c in list(self.fields_frame.children.values()):
            c.destroy()

    def _render_fields(self) -> None:
        self._clear_fields()
        self.field_rows: List[_FieldRow] = []
        preset = self._current_preset()
        for spec in list(preset.get("fields", [])):
            try:
                row = _FieldRow(self.fields_frame, spec)
            except Exception:
                # never break rendering – fall back to a text field
                row = _FieldRow(self.fields_frame, {"key": spec.get("key", "param"), "label": spec.get("label", "Param"), "type": "text"})
            self.field_rows.append(row)

        # lightweight periodic refresh so preview keeps in sync
        self.win.after(200, self._tick_preview)

    def _on_preset_change(self, _ev=None) -> None:
        self._render_fields()
        self._refresh_preview()

    def _values(self) -> Dict[str, Any]:
        vals: Dict[str, Any] = {}
        for r in self.field_rows:
            try:
                vals[r.key] = r.get_value()
            except Exception:
                pass
        return vals

    def _render_template(self, include_transcript: bool) -> str:
        preset = self._current_preset()
        template: str = str(preset.get("template", "")).strip()

        vals = self._values()
        defaults = {"audience": "", "tone": "", "length": "", "reading_level": "", "horizon": "", "days": ""}
        fmt = {**defaults, **vals}
        fmt["transcript"] = self.transcript if include_transcript else "[Transcript here]"

        try:
            return template.format(**fmt)
        except Exception:
            # if .format fails (e.g. stray braces), still return something useful
            base = template.replace("{transcript}", fmt["transcript"])
            meta = "\n".join(f"{k}={v}" for k, v in fmt.items() if k != "transcript")
            return f"{base}\n\nParameters:\n{meta}"

    def _refresh_preview(self) -> None:
        txt = self._render_template(include_transcript=False)
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", txt)
        self.preview.configure(state="disabled")

    def _tick_preview(self) -> None:
        # cheap polling to reflect field changes without wiring events for every control
        self._refresh_preview()
        self.win.after(350, self._tick_preview)

    # ----- actions -------------------------------------------------------------

    def _copy_prompt(self) -> None:
        txt = self._render_template(include_transcript=False)
        self.win.clipboard_clear()
        self.win.clipboard_append(txt)
        show_toast(self.win, "Prompt copied ✓")

    def _copy_prompt_with_transcript(self) -> None:
        txt = self._render_template(include_transcript=True)
        self.win.clipboard_clear()
        self.win.clipboard_append(txt)
        show_toast(self.win, "Prompt + transcript copied ✓")

    def _copy_transcript(self) -> None:
        self.win.clipboard_clear()
        self.win.clipboard_append(self.transcript)
        show_toast(self.win, "Transcript copied ✓")

    def _save_transcript(self) -> None:
        """Gathers data and saves the transcript to a file."""
        if not self.video_id:
            messagebox.showerror("Error", "Cannot save: Video ID is missing.", parent=self.win)
            return

        current_text = self.txt.get("1.0", "end-1c").strip()
        if not current_text:
            if not messagebox.askyesno("Confirm", "Transcript is empty. Save anyway?", parent=self.win):
                return

        try:
            tm = TranscriptsManager()
            wm = WinnersManager()
            winner = wm.get_winner_by_id(self.video_id)

            record = {
                "video_id": self.video_id,
                "title": self.video_title,
                "source_url": f"https://youtube.com/watch?v={self.video_id}",
                "channel_title": winner.channel_title if winner else "",
                "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "language": "en",  # Placeholder, as we don't know the language yet
                "duration": winner.duration if winner else "00:00:00",
                "tags": winner.tags if winner else [],
                "folder": winner.folder if winner else "Default",
                "notes": "", # Notes are not available in this window
                "text": current_text,
            }

            if tm.save(record):
                show_toast(self.win, "Transcript saved successfully.")
                # Optionally update the winner to mark has_transcript = True
                if winner:
                    setattr(winner, 'has_transcript', True)
                    wm.update_winner(self.video_id, winner.to_dict())

                if self.on_save_callback:
                    self.on_save_callback()
            else:
                messagebox.showerror("Error", "Failed to save transcript.", parent=self.win)

        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred:\n{e}", parent=self.win)


    # public/back-compat
    def show(self) -> None:
        try:
            self.win.deiconify()
        except Exception:
            pass


# ---------- Backwards-compat entry points ------------------------------------
# Keep ALL common names so whatever the old code calls will open this window.

def show_transcript_prompter(parent: tk.Tk, video_title: str, video_id: str, transcript: str) -> TranscriptDialog:
    dlg = TranscriptDialog(parent, video_title, video_id, transcript)
    dlg.show()
    return dlg

def open_transcript_prompter(parent: tk.Tk, video_title: str, video_id: str, transcript: str) -> TranscriptDialog:
    return show_transcript_prompter(parent, video_title, video_id, transcript)

def show_transcript_window(parent: tk.Tk, video_title: str, video_id: str, transcript: str) -> TranscriptDialog:
    return show_transcript_prompter(parent, video_title, video_id, transcript)

def open_transcript_window(parent: tk.Tk, video_title: str, video_id: str, transcript: str) -> TranscriptDialog:
    return show_transcript_prompter(parent, video_title, video_id, transcript)

def open_transcript_dialog(parent: tk.Tk, video_title: str, video_id: str, transcript: str) -> TranscriptDialog:
    return show_transcript_prompter(parent, video_title, video_id, transcript)

# Also expose a familiar alias some codebases used:
TranscriptPrompter = TranscriptDialog
