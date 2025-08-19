"""
Settings Window for the YouTube Clip Agent.

Provides a user interface for modifying application settings.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from data.settings_manager import settings_manager
from core.yt_dlp_helper import get_yt_dlp_version, update_yt_dlp
import threading
from datetime import datetime

class SettingsWindow(tk.Toplevel):
    """
    A Toplevel window for displaying and editing application settings.
    """
    def __init__(self, parent, winners_manager: 'WinnersManager', ui_call: callable):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("800x600")
        self.configure(bg="#1e1e1e")
        self.transient(parent)
        self.grab_set()

        self.ui_call = ui_call
        self.winners_manager = winners_manager
        self.settings = settings_manager.settings
        self.vars = {}

        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        # Main frame
        main_frame = tk.Frame(self, bg="#1e1e1e")
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True)

        # Create tabs
        appearance_tab = self._create_appearance_tab(notebook)
        paths_tab = self._create_paths_tab(notebook)
        search_tab = self._create_search_tab(notebook)
        library_tab = self._create_library_tab(notebook)

        notebook.add(appearance_tab, text="Appearance")
        notebook.add(paths_tab, text="Paths & API")
        notebook.add(search_tab, text="Search & Analysis")
        notebook.add(library_tab, text="Library")

        # Action buttons
        button_frame = tk.Frame(main_frame, bg="#1e1e1e")
        button_frame.pack(fill='x', pady=10)

        ttk.Button(button_frame, text="Save & Close", command=self._save_and_close).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side='right')

    def _create_appearance_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)

        # Theme
        ttk.Label(frame, text="Theme:").grid(row=0, column=0, sticky='w', pady=5)
        self.vars['theme_name'] = tk.StringVar()
        theme_combo = ttk.Combobox(frame, textvariable=self.vars['theme_name'],
                                   values=["onyx", "neon", "high_contrast", "light"], state="readonly")
        theme_combo.grid(row=0, column=1, sticky='ew', padx=5)

        # UI Scale
        ttk.Label(frame, text="UI Scale:").grid(row=1, column=0, sticky='w', pady=5)
        self.vars['ui_scale'] = tk.DoubleVar()
        scale_entry = ttk.Entry(frame, textvariable=self.vars['ui_scale'])
        scale_entry.grid(row=1, column=1, sticky='ew', padx=5)

        # Preview setting
        self.vars['preview_in_webview'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Open previews in embedded webview (recommended)",
                        variable=self.vars['preview_in_webview']).grid(row=2, column=0, columnspan=2, sticky='w', pady=10)

        # Font Sizes
        ttk.Label(frame, text="Font Sizes:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky='w', pady=10)

        font_sizes_frame = ttk.Frame(frame)
        font_sizes_frame.grid(row=3, column=0, columnspan=2, sticky='ew')

        self.vars['font_sizes'] = {}
        row = 0
        for size_key in ["base", "sm", "lg", "xl"]:
            ttk.Label(font_sizes_frame, text=f"{size_key.capitalize()}:").grid(row=row, column=0, sticky='w', pady=2)
            self.vars['font_sizes'][size_key] = tk.IntVar()
            entry = ttk.Entry(font_sizes_frame, textvariable=self.vars['font_sizes'][size_key], width=10)
            entry.grid(row=row, column=1, sticky='w', padx=5)
            row += 1

        return frame

    def _create_paths_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        frame.columnconfigure(1, weight=1)

        self.vars['api_keys'] = tk.StringVar()
        self.vars['yt_dlp_path'] = tk.StringVar()
        self.vars['ffmpeg_path'] = tk.StringVar()
        self.vars['cliphustle_base_path'] = tk.StringVar()

        # API Keys
        ttk.Label(frame, text="API Keys (one per line):").grid(row=0, column=0, columnspan=2, sticky='w', pady=5)
        api_keys_text = tk.Text(frame, height=5, width=60, bg="#2a2f37", fg="#e6e6e6", insertbackground="#e6e6e6")
        api_keys_text.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(0, 10))
        self.api_keys_text = api_keys_text

        # Paths
        paths = [
            ("yt_dlp_path", "yt-dlp Path", self._browse_file),
            ("ffmpeg_path", "FFmpeg Path", self._browse_file),
            ("cliphustle_base_path", "ClipHustle Base Path", self._browse_directory),
        ]

        row = 2
        for key, text, command in paths:
            ttk.Label(frame, text=f"{text}:").grid(row=row, column=0, sticky='w', pady=5)
            entry = ttk.Entry(frame, textvariable=self.vars[key])
            entry.grid(row=row, column=1, sticky='ew', padx=5)
            ttk.Button(frame, text="Browse...", command=lambda k=key: command(k)).grid(row=row, column=2, padx=5)
            row += 1

        # yt-dlp Management Section
        ttk.Separator(frame, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=15)
        row += 1

        ttk.Label(frame, text="yt-dlp Management", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky='w', pady=5)
        row += 1

        self.vars['yt_dlp_auto_update'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Auto-update yt-dlp on extractor errors (recommended)",
                        variable=self.vars['yt_dlp_auto_update']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)
        row += 1

        self.yt_dlp_version_label = ttk.Label(frame, text="Installed yt-dlp version: ...")
        self.yt_dlp_version_label.grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        row += 1

        self.yt_dlp_last_check_label = ttk.Label(frame, text="Last update check: ...")
        self.yt_dlp_last_check_label.grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        row += 1

        self.update_button = ttk.Button(frame, text="Check for Updates", command=self._check_for_yt_dlp_updates)
        self.update_button.grid(row=row, column=0, pady=10)
        row += 1

        ttk.Separator(frame, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=15)
        row += 1

        ttk.Label(frame, text="Debugging Info", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky='w', pady=5)
        row += 1

        ttk.Label(frame, text="Last Resolved Audio Path:").grid(row=row, column=0, sticky='w', pady=2)
        self.vars['last_resolved_audio_path'] = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.vars['last_resolved_audio_path'], state='readonly')
        entry.grid(row=row, column=1, columnspan=2, sticky='ew', padx=5)

        return frame

    def _check_for_yt_dlp_updates(self):
        """Handles the 'Check for Updates' button click."""
        self.update_button.config(state='disabled', text="Checking...")

        def _task():
            result = update_yt_dlp()
            self.ui_call(self._on_update_complete, result)

        threading.Thread(target=_task, daemon=True).start()

    def _on_update_complete(self, result):
        """Callback executed on the main thread after the update task finishes."""
        self.update_button.config(state='normal', text="Check for Updates")

        if result.success:
            messagebox.showinfo("yt-dlp Update", result.message, parent=self)
            # Refresh version info after update
            self._update_version_labels()
            settings_manager.set('yt_dlp_last_update_check', datetime.now().isoformat())
            self.yt_dlp_last_check_label.config(text=f"Last update check: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        else:
            messagebox.showerror("yt-dlp Update Failed", result.message, parent=self)

    def _create_search_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)

        self.vars['max_api_calls'] = tk.IntVar()
        self.vars['default_search_count'] = tk.IntVar()

        # Search settings
        ttk.Label(frame, text="Max API Calls:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(frame, textvariable=self.vars['max_api_calls']).grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(frame, text="Default Search Count:").grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(frame, textvariable=self.vars['default_search_count']).grid(row=1, column=1, sticky='w', padx=5)

        # Viral Score Weights
        ttk.Label(frame, text="Viral Score Weights:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky='w', pady=10)
        weights_frame = ttk.Frame(frame)
        weights_frame.grid(row=3, column=0, columnspan=2, sticky='w')
        self.vars['viral_score_weights'] = {}
        row = 0
        for key in self.settings['viral_score_weights']:
            ttk.Label(weights_frame, text=f"{key.capitalize()}:").grid(row=row, column=0, sticky='w', pady=2)
            self.vars['viral_score_weights'][key] = tk.DoubleVar()
            ttk.Entry(weights_frame, textvariable=self.vars['viral_score_weights'][key], width=10).grid(row=row, column=1, sticky='w', padx=5)
            row += 1

        ttk.Separator(frame, orient='horizontal').grid(row=row+4, column=0, columnspan=3, sticky='ew', pady=15)

        # Audio Download Settings
        ttk.Label(frame, text="Preferred Audio Format:", font=("Segoe UI", 10, "bold")).grid(row=row+5, column=0, sticky='w', pady=10)
        self.vars['preferred_audio_format'] = tk.StringVar()
        audio_format_combo = ttk.Combobox(frame, textvariable=self.vars['preferred_audio_format'],
                                   values=["m4a", "mp3", "wav"], state="readonly")
        audio_format_combo.grid(row=row+5, column=1, sticky='ew', padx=5)


        return frame

    def _update_version_labels(self):
        """Fetches and displays the yt-dlp version info."""
        def _task():
            version = get_yt_dlp_version() or "Not found"
            last_check = self.settings.get('yt_dlp_last_update_check')

            if last_check:
                try:
                    last_check_dt = datetime.fromisoformat(last_check)
                    last_check_str = last_check_dt.strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    last_check_str = "Never"
            else:
                last_check_str = "Never"

            def _update_labels():
                self.yt_dlp_version_label.config(text=f"Installed yt-dlp version: {version}")
                self.yt_dlp_last_check_label.config(text=f"Last update check: {last_check_str}")
                if version != "Not found":
                    settings_manager.set('yt_dlp_current_version', version)

            self.ui_call(_update_labels)

        threading.Thread(target=_task, daemon=True).start()

    def _load_settings(self):
        self._update_version_labels() # Fetch version info
        # Appearance
        self.vars['theme_name'].set(self.settings.get('theme_name'))
        self.vars['ui_scale'].set(self.settings.get('ui_scale'))
        self.vars['preview_in_webview'].set(self.settings.get('preview_in_webview', True)) # Default to True
        for key, var in self.vars['font_sizes'].items():
            var.set(self.settings.get('font_sizes', {}).get(key))

        # Paths & API
        self.vars['yt_dlp_auto_update'].set(self.settings.get('yt_dlp_auto_update', True))
        self.api_keys_text.insert('1.0', "\n".join(self.settings.get('api_keys', [])))
        self.vars['yt_dlp_path'].set(self.settings.get('yt_dlp_path'))
        self.vars['ffmpeg_path'].set(self.settings.get('ffmpeg_path'))
        self.vars['cliphustle_base_path'].set(self.settings.get('cliphustle_base_path'))
        self.vars['last_resolved_audio_path'].set(self.settings.get('last_resolved_audio_path', ''))

        # Search & Analysis
        self.vars['max_api_calls'].set(self.settings.get('max_api_calls'))
        self.vars['default_search_count'].set(self.settings.get('default_search_count'))
        self.vars['preferred_audio_format'].set(self.settings.get('preferred_audio_format', 'm4a'))
        for key, var in self.vars['viral_score_weights'].items():
            var.set(self.settings.get('viral_score_weights', {}).get(key))

        # Library
        self.vars['save_default_folder'].set(self.settings.get('save_default_folder'))
        self.vars['save_remember_last_folder'].set(self.settings.get('save_remember_last_folder'))
        self.vars['save_auto_download_transcript'].set(self.settings.get('save_auto_download_transcript'))
        self.vars['save_auto_open_prompt_builder'].set(self.settings.get('save_auto_open_prompt_builder'))

    def _save_and_close(self):
        try:
            # Appearance
            settings_manager.set('theme_name', self.vars['theme_name'].get())
            settings_manager.set('ui_scale', self.vars['ui_scale'].get())
            settings_manager.set('preview_in_webview', self.vars['preview_in_webview'].get())
            font_sizes = {key: var.get() for key, var in self.vars['font_sizes'].items()}
            settings_manager.set('font_sizes', font_sizes)

            # Paths & API
            settings_manager.set('yt_dlp_auto_update', self.vars['yt_dlp_auto_update'].get())
            api_keys = self.api_keys_text.get('1.0', tk.END).strip().split('\n')
            settings_manager.set('api_keys', [key for key in api_keys if key])
            settings_manager.set('yt_dlp_path', self.vars['yt_dlp_path'].get())
            settings_manager.set('ffmpeg_path', self.vars['ffmpeg_path'].get())
            settings_manager.set('cliphustle_base_path', self.vars['cliphustle_base_path'].get())

            # Search & Analysis
            settings_manager.set('max_api_calls', self.vars['max_api_calls'].get())
            settings_manager.set('default_search_count', self.vars['default_search_count'].get())
            settings_manager.set('preferred_audio_format', self.vars['preferred_audio_format'].get())
            viral_weights = {key: var.get() for key, var in self.vars['viral_score_weights'].items()}
            settings_manager.set('viral_score_weights', viral_weights)

            # Library
            settings_manager.set('save_default_folder', self.vars['save_default_folder'].get())
            settings_manager.set('save_remember_last_folder', self.vars['save_remember_last_folder'].get())
            settings_manager.set('save_auto_download_transcript', self.vars['save_auto_download_transcript'].get())
            settings_manager.set('save_auto_open_prompt_builder', self.vars['save_auto_open_prompt_builder'].get())

            messagebox.showinfo("Settings Saved", "Settings have been saved. Some changes may require a restart to take full effect.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error Saving", f"An error occurred while saving settings: {e}", parent=self)

    def _browse_file(self, key):
        path = filedialog.askopenfilename(parent=self)
        if path:
            self.vars[key].set(path)

    def _browse_directory(self, key):
        path = filedialog.askdirectory(parent=self)
        if path:
            self.vars[key].set(path)

    def _create_library_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Save Dialog Settings", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))

        # Default Folder
        ttk.Label(frame, text="Default Save Folder:").grid(row=1, column=0, sticky='w', pady=5)
        self.vars['save_default_folder'] = tk.StringVar()
        folder_combo = ttk.Combobox(frame, textvariable=self.vars['save_default_folder'],
                                    values=self.winners_manager.get_all_folders(), state="readonly")
        folder_combo.grid(row=1, column=1, sticky='ew', padx=5)

        # Toggles
        self.vars['save_remember_last_folder'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Remember last used folder", variable=self.vars['save_remember_last_folder']).grid(row=2, column=0, columnspan=2, sticky='w', pady=5)

        self.vars['save_auto_download_transcript'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Auto-download transcript on save (if not present)", variable=self.vars['save_auto_download_transcript']).grid(row=3, column=0, columnspan=2, sticky='w', pady=5)

        self.vars['save_auto_open_prompt_builder'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Auto-open Prompt Builder after save", variable=self.vars['save_auto_open_prompt_builder']).grid(row=4, column=0, columnspan=2, sticky='w', pady=5)

        return frame
