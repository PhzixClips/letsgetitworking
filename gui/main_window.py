"""
Main application window and GUI controller (no presets, free-form Count)
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import webview
from typing import Optional, Callable
import threading
import uuid

# --- App config & theme ---
from config import WINDOW_GEOMETRY, COLORS, UI_FONT_FAMILY, UI_FONT_SIZES, AUDIO_CLIPS_PATH
from gui.theme import apply_theme
from gui.settings_window import SettingsWindow
from data.settings_manager import settings_manager

# Core modules
from search.search_engine import SearchEngine
from media.media_processor import MediaProcessor
from analysis.video_analyzer import VideoAnalyzer
from gui.tab_manager import TabManager
import webbrowser
import webbrowser
from integrations.facebook_extractor import is_facebook_url, download_facebook_video, normalize_facebook_url
from integrations.facebook_helper import canonicalize_facebook_url
from core.yt_dlp_helper import run_metadata_dump, update_yt_dlp
from gui.components import (
    ProgressDialog, CaptionDialog, TimerWidget, show_toast, ManualTranscriptDialog, FolderManagerDialog
)
from gui.transcript_prompter import TranscriptDialog
from gui.preview_window import PreviewWindow
from utils.logging import Logger

from data.transcripts_manager import TranscriptsManager
# Winners (fallback if module not present)
try:
    from data.winners_manager import WinnersManager
except ImportError:
    class WinnersManager:
        def __init__(self, *_, **__): self.winners=[]
        def get_winner_count(self): return 0
        def get_all_folders(self): return ["Default"]
        def add_winner(self, *_, **__): return False
        def get_winner_by_id(self, *_, **__): return None
        def add_folder(self, *_, **__): return False
        def rename_folder(self, *_, **__): return False
        def remove_folder(self, *_, **__): return False
        def update_winner(self, *_, **__): return False


class MainWindow:
    """Main application window controller"""

    def __init__(self):
        self.logger = Logger("MainWindow")

        # Initialize components
        self.search_engine = SearchEngine()
        self.winners_manager = WinnersManager()
        self.media_processor = MediaProcessor()
        self.transcripts_manager = TranscriptsManager()

        # UI components
        self.root = None
        self.tab_manager = None
        self.progress_dialog = None
        self.timer_widget = None

        # Search state
        self.current_search_active = False
        self.yt_dlp_updated_this_session = False

        # --- Widget references for dynamic updates ---
        self.url_label = None
        self.url_entry = None
        self.query_label = None
        self.query_entry = None
        self.uploaded_label = None
        self.date_combo = None
        self.count_label = None
        self.count_entry = None
        self.vph_label = None
        self.vph_entry = None
        self.max_duration_label = None
        self.max_duration_entry = None
        self.generate_button = None
        self.action_buttons = {}
        self.winners_counter_label = None
        self.tab_counter_label = None
        self.status_message_frame = None
        self.status_message_label = None
        self.undo_button = None
        self.status_job = None
        self.url_frame = None
        self.search_frame = None

        # --- Facebook specific UI ---
        self.facebook_options_frame = None
        self.use_facebook_cookies_var = None
        self.facebook_cookies_path_var = None


    def ui_call(self, func: Callable, *args, **kwargs):
        """
        Schedule a callable on the Tk UI thread ASAP.
        Safe to call from worker threads.
        """
        try:
            if self.ui and self.ui.winfo_exists():
                self.ui.after(0, lambda: func(*args, **kwargs))
        except Exception as e:
            # Use f-string as our logger expects a single string.
            self.logger.error(f"ui_call failure: {e}")

    # -----------------------------
    # App lifecycle
    # -----------------------------
    def run(self):
        self._create_gui()
        self.root.mainloop()

    def _create_gui(self):
        self.root = tk.Tk()
        self.ui = self.root  # Expose root widget for safe UI calls
        self.root.title('YouTube Clip Agent - Modular Edition')
        self.root.geometry(WINDOW_GEOMETRY)

        # Apply global ttk theme + scaling BEFORE creating ttk widgets
        try:
            apply_theme(self.root)
        except Exception as e:
            self.logger.error(f"Theme apply error (continuing with defaults): {e}")

        # Create main components
        self._create_url_input()
        self._create_search_controls()
        self._create_tab_system()
        self._create_action_buttons()
        self._create_status_bar()

        # Apply settings (styles, fonts, colors)
        self._apply_live_settings()

        # Initialize Winners tab and load data
        self._initialize_winners_tab()

        # Initial results tab
        self.tab_manager.add_new_tab("Search Results")

        self.logger.info("GUI initialized successfully")

    # -----------------------------
    # Styles & Settings Application
    # -----------------------------
    def _apply_live_settings(self):
        """Applies settings that can be changed dynamically."""
        # Reload settings in case they changed
        from config import COLORS, UI_FONT_FAMILY, UI_FONT_SIZES

        self.root.configure(bg=COLORS.get('bg_primary', '#16181d'))
        self._configure_styles(COLORS, UI_FONT_FAMILY, UI_FONT_SIZES)
        self._update_widget_fonts(COLORS, UI_FONT_FAMILY, UI_FONT_SIZES)

    def _configure_styles(self, colors, font_family, font_sizes):
        """Configure ttk styles with current palette and fix white-on-white"""
        style = ttk.Style()

        font_sm = (font_family, font_sizes['sm'])
        font_sm_bold = (font_family, font_sizes['sm'], 'bold')

        # Treeview base
        style.configure(
            'Treeview',
            background=colors.get('bg_primary', '#16181d'),
            foreground=colors.get('fg_primary', '#e6e6e6'),
            fieldbackground=colors.get('bg_secondary', '#1f232a'),
            rowheight=24,
            font=font_sm
        )
        style.map(
            'Treeview',
            background=[('selected', colors.get('bg_accent', '#2d6cdf'))],
            foreground=[('selected', colors.get('fg_on_accent', '#ffffff'))]
        )

        # Treeview header
        style.configure(
            'Treeview.Heading',
            background=colors.get('bg_primary', '#16181d'),
            foreground=colors.get('fg_accent', '#fbbf24'),
            relief='flat',
            font=font_sm_bold
        )

        # Buttons
        style.configure('TButton', padding=(10, 6), font=font_sm)
        style.map('TButton', relief=[('pressed', 'sunken'), ('active', 'raised')])

        style.configure('Secondary.TButton', padding=(10, 8)) # Taller for URL bar

        # Dark combobox style
        style_name = 'Dark.TCombobox'
        style.configure(
            style_name,
            fieldbackground=colors.get('bg_secondary', '#1f232a'),
            background=colors.get('bg_secondary', '#1f232a'),
            foreground=colors.get('fg_primary', '#e6e6e6')
        )
        style.map(
            style_name,
            fieldbackground=[('readonly', colors.get('bg_secondary', '#1f232a')),
                             ('!disabled', colors.get('bg_secondary', '#1f232a'))],
            foreground=[('readonly', colors.get('fg_primary', '#e6e6e6')),
                        ('!disabled', colors.get('fg_primary', '#e6e6e6'))],
            background=[('active', colors.get('bg_secondary', '#1f232a'))]
        )
        self.combobox_style = style_name

    def _update_widget_fonts(self, colors, font_family, font_sizes):
        """Update fonts for widgets that don't use ttk styles."""
        font_base = (font_family, font_sizes['base'])
        font_base_bold = (font_family, font_sizes['base'], 'bold')
        font_sm = (font_family, font_sizes['sm'])
        font_sm_bold = (font_family, font_sizes['sm'], 'bold')

        # URL Input
        if self.url_label: self.url_label.config(font=font_base_bold)
        if self.url_entry: self.url_entry.config(font=font_base)

        # Search Controls
        if self.query_label: self.query_label.config(font=font_sm)
        if self.query_entry: self.query_entry.config(font=font_sm)
        if self.uploaded_label: self.uploaded_label.config(font=font_sm)
        if self.count_label: self.count_label.config(font=font_sm)
        if self.count_entry: self.count_entry.config(font=font_sm)
        if self.vph_label: self.vph_label.config(font=font_sm)
        if self.vph_entry: self.vph_entry.config(font=font_sm)
        if self.max_duration_label: self.max_duration_label.config(font=font_sm)
        if self.max_duration_entry: self.max_duration_entry.config(font=font_sm)
        if self.generate_button: self.generate_button.config(font=font_base_bold)

        # Action Buttons
        for text, button in self.action_buttons.items():
            is_winner_btn = text.startswith('🏆')
            button.config(font=font_sm_bold if is_winner_btn else font_sm)

        # Status Bar
        if self.winners_counter_label: self.winners_counter_label.config(font=font_sm_bold)
        if self.tab_counter_label: self.tab_counter_label.config(font=font_sm)

    # -----------------------------
    # Top: URL section
    # -----------------------------
    def _create_url_input(self):
        # --- Main URL Frame ---
        url_input_frame = tk.Frame(self.root, bg=COLORS.get('bg_primary', '#16181d'))
        url_input_frame.pack(fill='x', padx=10, pady=(8, 0)) # Reduced bottom padding

        self.url_label = tk.Label(url_input_frame, text='🔗 URL:', bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_accent', '#fbbf24'))
        self.url_label.pack(side='left')

        self.url_entry = tk.Entry(url_input_frame, width=60, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6'))
        self.url_entry.pack(side='left', padx=8, ipady=4)

        analyze_button = ttk.Button(url_input_frame, text='Analyze URL', command=self._analyze_url, style="Secondary.TButton")
        analyze_button.pack(side='left', padx=6)

        # --- Facebook Advanced Options (initially hidden) ---
        self.facebook_options_frame = tk.Frame(self.root, bg=COLORS.get('bg_primary', '#16181d'))
        # self.facebook_options_frame.pack(fill='x', padx=10, pady=(2, 4)) # Packed on demand

        self.use_facebook_cookies_var = tk.BooleanVar(value=False)
        self.facebook_cookies_path_var = tk.StringVar(value=settings_manager.get('facebook_cookies_path', ''))

        fb_cookie_check = ttk.Checkbutton(self.facebook_options_frame, text="Use cookies for Facebook", variable=self.use_facebook_cookies_var)
        fb_cookie_check.pack(side='left', padx=(60, 10))

        fb_cookie_entry = tk.Entry(self.facebook_options_frame, textvariable=self.facebook_cookies_path_var, width=40, state='readonly', bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_secondary', '#b7bdc6'))
        fb_cookie_entry.pack(side='left', ipady=2)

        def _browse_cookies():
            filepath = filedialog.askopenfilename(
                title="Select cookies.txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialdir=Path.home()
            )
            if filepath:
                self.facebook_cookies_path_var.set(filepath)
                settings_manager.set('facebook_cookies_path', filepath)

        browse_btn = ttk.Button(self.facebook_options_frame, text='Browse...', command=_browse_cookies)
        browse_btn.pack(side='left', padx=6)

        # --- URL Entry Behaviors ---
        def _update_ui_on_key_release(*args):
            url = self.url_entry.get()
            state = 'disabled' if not url else 'normal'
            analyze_button.config(state=state)

            if is_facebook_url(url):
                if not self.facebook_options_frame.winfo_ismapped():
                    self.facebook_options_frame.pack(fill='x', padx=10, pady=(2, 4), before=self.search_frame)
                self.url_label.config(text="🔗 FB URL:")
            else:
                if self.facebook_options_frame.winfo_ismapped():
                    self.facebook_options_frame.pack_forget()
                self.url_label.config(text="🔗 URL:")

        self.url_entry.bind('<KeyRelease>', _update_ui_on_key_release)
        self.url_entry.bind('<Escape>', lambda e: self._clear_url())

        # Right-click menu
        url_menu = tk.Menu(self.root, tearoff=0)
        url_menu.add_command(label="Paste", command=lambda: self.url_entry.event_generate('<<Paste>>'))
        url_menu.add_command(label="Clear", command=self._clear_url)
        self.url_entry.bind("<Button-3>", lambda e: url_menu.tk_popup(e.x_root, e.y_root))

        _update_ui_on_key_release() # Set initial state

        separator = tk.Frame(self.root, height=2, bg=COLORS.get('border', '#3a3a3a'))
        separator.pack(fill='x', padx=10, pady=(6, 8))

    # -----------------------------
    # Search controls row
    # -----------------------------
    def _create_search_controls(self):
        self.search_frame = tk.Frame(self.root, bg=COLORS.get('bg_primary', '#16181d'))
        self.search_frame.pack(fill='x', padx=10, pady=4)

        self.query_label = tk.Label(self.search_frame, text='Search:', bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6'))
        self.query_label.pack(side='left')
        self.query_entry = tk.Entry(self.search_frame, width=25, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6'))
        self.query_entry.pack(side='left', padx=6)

        self.uploaded_label = tk.Label(self.search_frame, text='Uploaded:', bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6'))
        self.uploaded_label.pack(side='left', padx=(12, 0))
        self.date_combo = ttk.Combobox(self.search_frame, values=['Any', '24h', '2d', '7d'], width=5, state="readonly")
        self.date_combo.set('Any')
        self.date_combo.pack(side='left', padx=6)

        self.count_label = tk.Label(self.search_frame, text='Count:', bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6'))
        self.count_label.pack(side='left', padx=(12, 0))
        self.count_entry = tk.Entry(self.search_frame, width=6, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6'))
        self.count_entry.insert(0, "50")
        self.count_entry.pack(side='left', padx=6)

        self.vph_label = tk.Label(self.search_frame, text='Min VPH:', bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6'))
        self.vph_label.pack(side='left', padx=(12, 0))
        self.vph_entry = tk.Entry(self.search_frame, width=6, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6'))
        self.vph_entry.pack(side='left', padx=6)

        self.max_duration_label = tk.Label(self.search_frame, text='Max Duration (s):', bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6'))
        self.max_duration_label.pack(side='left', padx=(12, 0))
        self.max_duration_entry = tk.Entry(self.search_frame, width=6, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6'))
        self.max_duration_entry.pack(side='left', padx=6)

        self.generate_button = tk.Button(self.search_frame, text='Generate', bg=COLORS.get('success', 'green'), fg=COLORS.get('fg_on_accent', '#ffffff'), command=self._start_search)
        self.generate_button.pack(side='left', padx=10)

    # -----------------------------
    # Tabs + results table
    # -----------------------------
    def _create_tab_system(self):
        self.tree_container = tk.Frame(self.root, bg=COLORS.get('bg_primary', '#16181d'))
        self.tree_container.pack(fill='both', expand=True, padx=8, pady=8)
        self.tab_manager = TabManager(self, self.root, self.tree_container, self.winners_manager, on_tab_switch=self._on_tab_switch)

    def _on_tab_switch(self, tab_data: Optional[dict]):
        """Callback for when the active tab changes."""
        # Guard clause to prevent crash on startup
        url_frame = getattr(self, "url_frame", None)
        search_frame = getattr(self, "search_frame", None)
        if not all(frame and frame.winfo_exists() for frame in [url_frame, search_frame]):
            return

        is_library_tab = tab_data and tab_data.is_winners_tab

        # Usingwinfo_ismapped() checks if the widget is currently visible
        if is_library_tab:
            if url_frame.winfo_ismapped():
                url_frame.pack_forget()
            if search_frame.winfo_ismapped():
                search_frame.pack_forget()
        else:
            if not url_frame.winfo_ismapped():
                url_frame.pack(fill='x', padx=10, pady=(8, 4), before=self.tree_container)
            if not search_frame.winfo_ismapped():
                search_frame.pack(fill='x', padx=10, pady=4, before=self.tree_container)

    # -----------------------------
    # Bottom action buttons
    # -----------------------------
    def _create_action_buttons(self):
        button_frame = tk.Frame(self.root, bg=COLORS.get('bg_primary', '#16181d'))
        button_frame.pack(fill='x', pady=6)

        left_frame = tk.Frame(button_frame, bg=COLORS.get('bg_primary', '#16181d'))
        left_frame.pack(side='left')

        buttons = [
            ('Preview', '#3B82F6', self._preview_video),
            ('Download', '#3B82F6', self._download_video),
            ('Transcribe', '#7C3AED', self._transcribe_video),
            ('Find Raw', '#A16207', self._find_raw_source),
            ('Library', '#FFD700', self._save_to_winners),
            ('Load Scripts', '#10B981', self._load_selected_transcripts),
            ('Open Folder', '#222', self._open_clip_folder)
        ]

        for text, color, command in buttons:
            is_primary = text == 'Library'
            btn = tk.Button(left_frame, text=text, bg=color, fg=('#000' if is_primary else COLORS.get('fg_on_accent', '#ffffff')), command=command, padx=10, pady=6, relief='flat', bd=0)
            btn.pack(side='left', padx=6)
            self.action_buttons[text] = btn

    # -----------------------------
    # Status bar
    # -----------------------------
    def _create_status_bar(self):
        status_frame = tk.Frame(self.root, bg=COLORS.get('bg_primary', '#16181d'))
        status_frame.pack(fill='x', padx=12, pady=(0, 6))

        left_frame = tk.Frame(status_frame, bg=COLORS.get('bg_primary', '#16181d'))
        left_frame.pack(side='left')

        self.winners_counter_label = tk.Label(left_frame, text='Library • 0 items', fg='#FFD700', bg=COLORS.get('bg_primary', '#16181d'))
        self.winners_counter_label.pack(side='left', padx=(0, 18))

        self.status_message_frame = tk.Frame(status_frame, bg=COLORS.get('bg_primary', '#16181d'))
        self.status_message_frame.pack(side='left', expand=True, fill='x', padx=20)

        right_frame = tk.Frame(status_frame, bg=COLORS.get('bg_primary', '#16181d'))
        right_frame.pack(side='right', padx=10)

        self.tab_counter_label = tk.Label(right_frame, text='Tabs: 0', fg='#A3A3A3', bg=COLORS.get('bg_primary', '#16181d'))
        self.tab_counter_label.pack(side='left', padx=(0, 18))

        self.timer_widget = TimerWidget(right_frame)
        self.timer_widget.pack(side='left')

        ttk.Button(right_frame, text='Set Timer', command=self._set_timer).pack(side='left', padx=10)

        ttk.Button(right_frame, text='Settings', command=self._open_settings).pack(side='left', padx=10)

    def _open_settings(self):
        """Opens the settings window and applies changes upon closing."""
        settings_win = SettingsWindow(self.root, self.winners_manager, self.ui_call)
        self.root.wait_window(settings_win)
        # A restart is still recommended for theme changes to be perfect
        messagebox.showinfo("Settings Updated", "Live settings applied. A restart is recommended for all changes to take full effect.", parent=self.root)
        self._apply_live_settings()
        self._update_save_button_text()

    def _update_save_button_text(self):
        """Updates the 'Save to Library' button text with the last/default folder."""
        if 'Library' in self.action_buttons:
            button = self.action_buttons['Library']

            last_folder = settings_manager.get('save_last_used_folder', 'Default')
            if not settings_manager.get('save_remember_last_folder'):
                last_folder = settings_manager.get('save_default_folder', 'Default')

            button_text = f"Save to {last_folder} ▾"
            button.config(text=button_text)

    # --- The rest of the file remains the same ---
    def _initialize_winners_tab(self):
        try:
            winners_tab_id = self.tab_manager.create_winners_tab()
            self._load_winners_to_tab()
            winner_count = self.winners_manager.get_winner_count()
            self.winners_counter_label.config(text=f'Library • {winner_count} items')
            self.tab_manager.update_tab_status(
                winners_tab_id,
                f"{winner_count} saved",
                'complete' if winner_count > 0 else 'idle'
            )
        except Exception as e:
            self.logger.error(f"Error initializing winners tab: {e}")

    def _load_winners_to_tab(self):
        try:
            winners_tab = self.tab_manager.get_winners_tab()
            if not winners_tab:
                return
            self.tab_manager.clear_tab_results(winners_tab.tab_id)
            for winner in self.winners_manager.winners:
                self.tab_manager.add_winner_to_tab(winner.to_dict())
            self.tab_manager.update_folder_filter()
        except Exception as e:
            self.logger.error(f"Error loading winners to tab: {e}")

    def _save_to_winners(self):
        try:
            video = self.tab_manager.get_selected_video()
            if not video:
                messagebox.showinfo('Save to Library', 'Please select a video first.')
                return

            video_id = video.get('video_id', '')
            video_title = video.get('title', '')

            folders = self.winners_manager.get_all_folders()
            transcript_path = AUDIO_CLIPS_PATH / f"{video_id}_transcript.txt"
            has_transcript = transcript_path.exists()

            dialog_result = self._show_folder_selection_dialog(folders, video_title, has_transcript)
            if not dialog_result:
                return

            # --- Save or Update Winner ---
            existing_winner = self.winners_manager.get_winner_by_id(video_id)
            success = False
            is_update = False

            if existing_winner:
                is_update = True
                action = self._show_conflict_dialog(video_title)
                if action == 'skip': return

                if action == 'replace':
                    dialog_result['folder'] = existing_winner.folder

                success = self.winners_manager.update_winner(video_id, dialog_result)
            else:
                video_to_save = video.copy()
                video_to_save.update(dialog_result)
                success = self.winners_manager.add_winner(video_to_save, dialog_result['folder'], notes=dialog_result['notes'])

            # --- Post-Save Actions ---
            if success:
                # Update last used folder if setting is enabled
                if settings_manager.get('save_remember_last_folder'):
                    settings_manager.set('save_last_used_folder', dialog_result['folder'])

                self._pulse_winners_counter()
                self._load_winners_to_tab()

                winner_count = self.winners_manager.get_winner_count()
                self.winners_counter_label.config(text=f'Library • {winner_count} items')

                winners_tab_id = self.tab_manager.winners_tab_id
                if winners_tab_id:
                    self.tab_manager.update_tab_status(f"{winner_count} saved", 'complete')

                if is_update:
                    self._set_status_message(f"Successfully updated '{video_title[:30]}...'", None)
                else:
                    def undo_action():
                        if self.winners_manager.remove_winner(video_id):
                            self._pulse_winners_counter()
                            self._load_winners_to_tab()
                            winner_count = self.winners_manager.get_winner_count()
                            self.winners_counter_label.config(text=f'Library • {winner_count} items')
                            self._clear_status_message()
                            self._set_status_message("Save undone.", None)

                    display_title = dialog_result['display_title']
                    saved_as = f"'{display_title[:20]}...'" if len(display_title) > 20 else f"'{display_title}'"
                    self._set_status_message(f"Saved to {dialog_result['folder']} as {saved_as}", undo_action)

                if dialog_result.get('download_transcript'):
                    self._download_transcript_async(
                        video_id,
                        callback=lambda: self._open_prompt_builder(video_id, dialog_result['display_title']) if dialog_result.get('open_prompt_builder') else None
                    )
                elif dialog_result.get('open_prompt_builder'):
                    self._open_prompt_builder(video_id, dialog_result['display_title'])

            elif not is_update:
                messagebox.showerror('Error', 'Failed to save video to Library.')

        except Exception as e:
            self.logger.error(f"Error saving to winners: {e}")
            messagebox.showerror('Error', f'An unexpected error occurred: {e}')

    def _show_conflict_dialog(self, video_title: str) -> str:
        """Shows a dialog to resolve a save conflict."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Conflict: Video Exists")
        dialog.geometry("450x150")
        dialog.configure(bg=COLORS.get('bg_primary', '#16181d'))
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        result = ['skip'] # Default to skipping

        label = tk.Label(dialog, text=f"'{video_title[:40]}...' is already in the Library.", fg=COLORS.get('fg_primary'), bg=COLORS.get('bg_primary'))
        label.pack(pady=20)

        button_frame = tk.Frame(dialog, bg=COLORS.get('bg_primary', '#16181d'))
        button_frame.pack(pady=10)

        def set_action(action):
            result[0] = action
            dialog.destroy()

        ttk.Button(button_frame, text="Replace Metadata (Keep Folder)", command=lambda: set_action('replace')).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Overwrite (Update All)", command=lambda: set_action('overwrite')).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Skip", command=lambda: set_action('skip')).pack(side='right', padx=5)

        dialog.wait_window()
        return result[0]

    def _clear_status_message(self):
        if self.status_job:
            self.root.after_cancel(self.status_job)
            self.status_job = None

        for widget in self.status_message_frame.winfo_children():
            widget.destroy()

        self.status_message_label = None
        self.undo_button = None

    def _set_status_message(self, message: str, undo_command: Optional[callable] = None):
        self._clear_status_message()

        self.status_message_label = tk.Label(self.status_message_frame, text=message, fg=COLORS.get('fg_primary'), bg=COLORS.get('bg_primary'))
        self.status_message_label.pack(side='left')

        if undo_command:
            self.undo_button = tk.Button(self.status_message_frame, text="Undo", command=undo_command, bg=COLORS.get('bg_accent'), fg=COLORS.get('fg_on_accent'), relief='flat', font=(UI_FONT_FAMILY, UI_FONT_SIZES['sm']-1))
            self.undo_button.pack(side='left', padx=10)

        self.status_job = self.root.after(6000, self._clear_status_message)

    def _pulse_winners_counter(self):
        original_color = '#FFD700'
        accent_color = COLORS.get('success', 'green')

        self.winners_counter_label.config(fg=accent_color)
        self.root.after(250, lambda: self.winners_counter_label.config(fg=original_color))
        self.root.after(500, lambda: self.winners_counter_label.config(fg=accent_color))
        self.root.after(750, lambda: self.winners_counter_label.config(fg=original_color))

    def _show_folder_selection_dialog(self, folders: list, original_title: str, has_transcript: bool) -> Optional[dict]:
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title('Save to Library')
            dialog.geometry('550x650')
            dialog.configure(bg=COLORS.get('bg_primary', '#16181d'))
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()

            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")

            result = [None]

            main_frame = tk.Frame(dialog, bg=COLORS.get('bg_primary', '#16181d'))
            main_frame.pack(fill='both', expand=True, padx=20, pady=10)

            # --- Form fields ---
            tk.Label(main_frame, text="Display Title", bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6')).pack(anchor='w')
            title_var = tk.StringVar(value=original_title)
            tk.Entry(main_frame, textvariable=title_var, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6')).pack(fill='x', pady=(2, 8))

            tk.Label(main_frame, text="Folder", bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6')).pack(anchor='w')
            listbox_frame = tk.Frame(main_frame)
            listbox_frame.pack(fill='both', expand=True, pady=(2, 8))
            listbox = tk.Listbox(listbox_frame, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), selectbackground=COLORS.get('bg_accent', '#2d6cdf'), selectforeground=COLORS.get('fg_on_accent', '#ffffff'), exportselection=False)
            scrollbar = tk.Scrollbar(listbox_frame, command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)

            def populate_listbox(select_item=None):
                current_selection_index = listbox.curselection()
                listbox.delete(0, tk.END)
                for folder in folders: listbox.insert(tk.END, folder)
                if select_item and select_item in folders:
                    idx = folders.index(select_item)
                    listbox.select_set(idx)
                    listbox.see(idx)
                elif current_selection_index:
                    listbox.select_set(current_selection_index[0])

            populate_listbox()
            listbox.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            tk.Label(main_frame, text="Tags (comma-separated)", bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6')).pack(anchor='w')
            tags_var = tk.StringVar()
            tk.Entry(main_frame, textvariable=tags_var, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6')).pack(fill='x', pady=(2, 8))

            tk.Label(main_frame, text="Notes", bg=COLORS.get('bg_primary', '#16181d'), fg=COLORS.get('fg_primary', '#e6e6e6')).pack(anchor='w')
            notes_text = tk.Text(main_frame, height=3, bg=COLORS.get('bg_secondary', '#1f232a'), fg=COLORS.get('fg_primary', '#e6e6e6'), insertbackground=COLORS.get('fg_primary', '#e6e6e6'), wrap='word')
            notes_text.pack(fill='x', expand=True, pady=(2, 8))

            # --- Transcript options ---
            transcript_frame = tk.Frame(main_frame, bg=COLORS.get('bg_primary'))
            transcript_frame.pack(fill='x', pady=5)
            download_transcript_var = tk.BooleanVar(value=settings_manager.get('save_auto_download_transcript'))
            open_prompt_builder_var = tk.BooleanVar(value=settings_manager.get('save_auto_open_prompt_builder'))

            if has_transcript:
                tk.Label(transcript_frame, text="✓ Transcript available", fg=COLORS.get('success', 'green'), bg=COLORS.get('bg_primary')).pack(side='left')
                download_transcript_var.set(False) # Can't download if it exists
            else:
                ttk.Checkbutton(transcript_frame, text="Download transcript after save", variable=download_transcript_var).pack(side='left')

            ttk.Checkbutton(transcript_frame, text="Open in Prompt Builder after save", variable=open_prompt_builder_var).pack(side='right')

            # --- Set initial folder selection based on settings ---
            initial_folder = None
            if settings_manager.get('save_remember_last_folder'):
                initial_folder = settings_manager.get('save_last_used_folder')
            else:
                initial_folder = settings_manager.get('save_default_folder')

            if initial_folder and initial_folder in folders:
                idx = folders.index(initial_folder)
                listbox.select_set(idx)
                listbox.see(idx)

            # --- Buttons ---
            button_frame = tk.Frame(dialog, bg=COLORS.get('bg_primary', '#16181d'))
            button_frame.pack(fill='x', padx=20, pady=(10, 15))

            def on_save(event=None):
                if listbox.curselection():
                    result[0] = {
                        "folder": folders[listbox.curselection()[0]],
                        "display_title": title_var.get().strip(),
                        "notes": notes_text.get("1.0", tk.END).strip(),
                        "tags": [t.strip() for t in tags_var.get().split(',') if t.strip()],
                        "download_transcript": download_transcript_var.get(),
                        "open_prompt_builder": open_prompt_builder_var.get()
                    }
                    dialog.destroy()

            save_button = ttk.Button(button_frame, text='Save', command=on_save, state='disabled')

            def on_new_folder():
                new_folder_name = simpledialog.askstring('New Folder', 'Enter folder name:', parent=dialog)
                if new_folder_name and new_folder_name.strip():
                    if self.winners_manager.add_folder(new_folder_name.strip()):
                        nonlocal folders
                        folders = self.winners_manager.get_all_folders()
                        populate_listbox(select_item=new_folder_name.strip())
                        update_save_button_state()
                    else:
                        messagebox.showerror('Error', 'Folder already exists or is invalid.', parent=dialog)

            def update_save_button_state(event=None):
                save_button.config(state='normal' if listbox.curselection() else 'disabled')

            listbox.bind('<<ListboxSelect>>', update_save_button_state)
            listbox.bind('<Double-1>', on_save)
            dialog.bind('<Return>', lambda e: on_save())
            dialog.bind('<Escape>', lambda e: dialog.destroy())

            # --- Final layout ---
            new_folder_button = ttk.Button(button_frame, text='New Folder', command=on_new_folder)
            cancel_button = ttk.Button(button_frame, text='Cancel', command=dialog.destroy)
            new_folder_button.pack(side='left', padx=(0, 20))
            save_button.pack(side='right', padx=6)
            cancel_button.pack(side='right')

            update_save_button_state()
            dialog.wait_window()
            return result[0]
        except Exception as e:
            self.logger.error(f"Error in folder selection dialog: {e}")
            return None

    def _extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'm\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m: return m.group(1)
        return None

    def _clear_url(self):
        self.url_entry.delete(0, tk.END)

    def _analyze_url(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning('No URL', 'Please enter a URL!')
            return
        if self.current_search_active:
            messagebox.showwarning('Analysis Active', 'An analysis is already in progress!')
            return

        # --- Set up tab for analysis ---
        active_tab_obj = self.tab_manager.get_active_tab()
        if not active_tab_obj or (active_tab_obj.search_term and "URL:" not in active_tab_obj.search_term):
             tab_id = self.tab_manager.add_new_tab("URL Analysis")
             active_tab_obj = self.tab_manager.get_active_tab() # Re-fetch the new tab object
        else:
             tab_id = self.tab_manager.get_active_tab_id()

        if not tab_id or not active_tab_obj:
             messagebox.showerror("Error", "Could not determine active tab.")
             return

        # Use f-string for logging, as the custom logger doesn't support printf-style args.
        self.logger.debug(f"Analyze URL: resolved active tab id={tab_id}")
        self.tab_manager.clear_tab_results(tab_id)

        # --- Route to correct analyzer ---
        if is_facebook_url(url):
            normalized_url = normalize_facebook_url(url)
            active_tab_obj.search_term = f"URL: {normalized_url.split('?')[0][-20:]}"
            active_tab_obj.label.config(text=f"FB URL: ...{normalized_url[-20:]}")
            self._perform_facebook_analysis(normalized_url)
        else:
            video_id = self._extract_video_id(url)
            if not video_id:
                messagebox.showerror('Invalid URL', 'Please enter a valid YouTube or Facebook URL!')
                return

            active_tab_obj.search_term = f"URL: {video_id}"
            active_tab_obj.label.config(text=f"YT URL: {video_id}")
            self._perform_youtube_analysis(video_id)

    def _perform_facebook_analysis(self, url: str):
        self.current_search_active = True
        tab_id = self.tab_manager.get_active_tab_id()
        if not tab_id:
            self.current_search_active = False
            return

        self.tab_manager.update_tab_status(tab_id, "Analyzing FB URL...", 'loading')
        self.progress_dialog = ProgressDialog(self.root, "🔍 Analyzing Facebook URL")
        self.progress_dialog.update_status("Starting Facebook analysis...")

        # Create and run the analysis task in a separate thread
        task = FacebookAnalysisTask(self, url)
        threading.Thread(target=task.run, daemon=True).start()

    def _finish_facebook_analysis(self, result):
        self.current_search_active = False
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        tab_id = self.tab_manager.get_active_tab_id()
        if not tab_id: return

        if 'error' in result:
            error_type = result.get("error")
            error_message = result.get("message", "Unknown error.")
            self.logger.error(f"Facebook analysis error: {error_type} - {error_message}")
            self.tab_manager.update_tab_status(tab_id, "Error", 'error')
            if error_type == "private_video":
                messagebox.showerror("❌ Analysis Error", "This video is private. Please provide a cookies.txt file for access.")
            else:
                messagebox.showerror("❌ Analysis Error", f"Could not analyze Facebook URL: {error_type}")
            return

        video_entry = VideoAnalyzer.process_facebook_video_data(result)
        if not video_entry:
            self.tab_manager.update_tab_status(tab_id, "Processing Error", 'error')
            messagebox.showerror("❌ Analysis Error", "Failed to process the extracted Facebook video data.")
            return

        self.tab_manager.add_result_to_tab(tab_id, video_entry)
        video_title = video_entry.get('title', 'Unknown')[:30]
        self.tab_manager.update_tab_status(tab_id, f"✓ {video_title}...", 'complete')
        messagebox.showinfo("✅ Analysis Complete", f"Successfully analyzed Facebook video:\n{video_title}")

    def _perform_youtube_analysis(self, video_id: str):
        self.current_search_active = True
        tab_id = self.tab_manager.get_active_tab_id()
        if not tab_id:
            self.current_search_active = False
            return
        try:
            self.tab_manager.update_tab_status(tab_id, "Analyzing URL...", 'loading')
            self.progress_dialog = ProgressDialog(self.root, "🔍 Analyzing YouTube URL")
            self.progress_dialog.update_status("Fetching video data...")

            video_details_map = self.search_engine.api_client.get_video_details([video_id])
            if not video_details_map or video_id not in video_details_map:
                self._finish_youtube_analysis([], error="Video not found or unavailable")
                return

            self.progress_dialog.update_status("Processing video data...")
            video_details = video_details_map[video_id]
            video_entry = VideoAnalyzer.process_video_data(video_details, video_id)
            if not video_entry:
                self._finish_youtube_analysis([], error="Failed to process video data")
                return

            self._finish_youtube_analysis([video_entry])
        except Exception as e:
            self.logger.error(f"URL analysis error: {e}")
            self._finish_youtube_analysis([], error=str(e))

    def _finish_youtube_analysis(self, results, error=None):
        self.current_search_active = False
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        tab_id = self.tab_manager.get_active_tab_id()
        if not tab_id: return

        try:
            if error:
                self.tab_manager.update_tab_status(tab_id, "Error", 'error')
                messagebox.showerror("❌ Analysis Error", f"Error analyzing URL: {error}")
                return

            for video in results:
                self.tab_manager.add_result_to_tab(tab_id, video)

            if results:
                video_title = results[0].get('title', 'Unknown')[:30]
                self.tab_manager.update_tab_status(tab_id, f"✓ {video_title}...", 'complete')
                messagebox.showinfo("✅ Analysis Complete", f"Successfully analyzed video:\n{video_title}")
            else:
                self.tab_manager.update_tab_status(tab_id, "No data", 'error')
                messagebox.showwarning("⚠️ No Data", "No video data found")

            self.tab_counter_label.config(text=f"Tabs: {self.tab_manager.get_tab_count()}")
        except Exception as e:
            self.logger.error(f"Error finishing URL analysis: {e}")
            self.tab_manager.update_tab_status(tab_id, "Error", 'error')

    def _start_search(self):
        if self.current_search_active:
            messagebox.showwarning('Search Active', 'A search is already in progress!')
            return

        query = self.query_entry.get().strip()
        if not query:
            messagebox.showwarning('No Query', 'Please enter a search query!')
            return

        active_tab_obj = self.tab_manager.get_active_tab()
        if active_tab_obj and (not active_tab_obj.search_term or active_tab_obj.search_term != query):
            active_tab_obj.search_term = query
            active_tab_obj.label.config(text=query[:15] + "..." if len(query) > 15 else query)
            tab_id = self.tab_manager.get_active_tab_id()
        else:
            tab_id = self.tab_manager.add_new_tab(query)

        if tab_id:
            self.tab_manager.clear_tab_results(tab_id)

        self._perform_search(query)

    def _perform_search(self, query: str):
        self.current_search_active = True
        active_tab = self.tab_manager.get_active_tab()
        if not active_tab:
            self.current_search_active = False
            return

        try:
            self.tab_manager.update_tab_status(active_tab.tab_id, "Searching...", 'loading')

            self.progress_dialog = ProgressDialog(self.root, "🔍 Search in Progress")
            try:
                self.progress_dialog.set_cancel_callback(self._cancel_search)
            except Exception:
                pass

            self.search_engine.reset_search()

            published_after = self._get_published_after()
            try:
                max_duration = int(self.max_duration_entry.get()) if self.max_duration_entry.get() else None
            except ValueError:
                max_duration = None

            try:
                desired_count = int(self.count_entry.get().strip() or "0")
            except ValueError:
                desired_count = 0

            try:
                min_vph = float(self.vph_entry.get() or 0)
            except ValueError:
                min_vph = 0.0

            def progress_callback(found_count, total_target, status_text=None):
                if self.progress_dialog:
                    if status_text:
                        self.progress_dialog.update_status(status_text)
                    if found_count >= 0:
                        progress_text = (
                            f"📊 Found: {found_count}/{total_target} videos | "
                            f"API calls: {self.search_engine.api_client.api_call_count}/100"
                        )
                        self.progress_dialog.update_progress_info(progress_text)
                        progress_percentage = min((self.search_engine.api_client.api_call_count / 100) * 100, 100)
                        self.progress_dialog.update_progress_bar(progress_percentage)

            self.root.after(100, lambda: self._do_search_async(
                query, desired_count, published_after, min_vph, max_duration, progress_callback
            ))
        except Exception as e:
            self.logger.error(f"Search setup error: {e}")
            self._finish_search([], error=str(e))

    def _do_search_async(self, query: str, desired_count: int, published_after,
                         min_vph: float, max_duration, progress_callback):
        try:
            results = self.search_engine.smart_search_fill(
                query, desired_count, published_after, min_vph, max_duration, progress_callback
            )
            self._finish_search(results)
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            self._finish_search([], error=str(e))

    def _finish_search(self, results, error=None):
        self.current_search_active = False
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        active_tab = self.tab_manager.get_active_tab()
        if not active_tab: return

        try:
            if error:
                self.tab_manager.update_tab_status(active_tab.tab_id, "Error", 'error')
                messagebox.showerror("❌ Search Error", f"Error during search: {error}")
                return

            for video in results:
                self.tab_manager.add_result_to_tab(active_tab.tab_id, video)

            api_calls = self.search_engine.api_client.api_call_count
            if self.search_engine.api_client.search_cancelled:
                self.tab_manager.update_tab_status(active_tab.tab_id, f"{len(results)} partial", 'error')
                messagebox.showwarning(
                    "⚠️ Search Cancelled",
                    f"Search stopped. Found {len(results)} videos using {api_calls} API calls"
                )
            else:
                self.tab_manager.update_tab_status(active_tab.tab_id, f"{len(results)} results", 'complete')
                messagebox.showinfo(
                    "✅ Search Complete",
                    f"Found {len(results)} videos using {api_calls} API calls"
                )

            self.tab_counter_label.config(text=f"Tabs: {self.tab_manager.get_tab_count()}")
        except Exception as e:
            self.logger.error(f"Error finishing search: {e}")
            self.tab_manager.update_tab_status(active_tab.tab_id, "Error", 'error')

    def _cancel_search(self):
        self.search_engine.cancel_search()
        if self.progress_dialog:
            self.progress_dialog.update_status("🛑 Cancelling search...")

    def _get_published_after(self) -> Optional[datetime]:
        v = self.date_combo.get()
        if v == 'Any': return None
        now = datetime.now(timezone.utc)
        return now - (timedelta(days=1) if v == '24h'
                      else timedelta(days=2) if v == '2d'
                      else timedelta(days=7) if v == '7d'
                      else timedelta(0))

    def _preview_video(self):
        # This method is now deprecated in favor of _show_preview
        # but is kept for the old button binding.
        self._show_preview()

    def _on_row_double_click(self, event):
        """Event handler for double-clicking a row in any results tree."""
        # The event is passed but not used, as we operate on the selected item.
        self._show_preview()

    def _show_preview(self):
        """Shows a preview for the selected video."""
        video = self.tab_manager.get_selected_video()
        if not video:
            messagebox.showinfo('Preview', 'Please select a video to preview.')
            return

        platform = video.get('platform', 'YouTube')
        url = video.get('webpage_url')
        if not url:
            if platform == 'YouTube':
                video_id = video.get('video_id')
                url = f'https://www.youtube.com/watch?v={video_id}'
            else:
                messagebox.showerror('Preview Error', 'No URL found for this item.')
                return

        title = video.get('title', 'Untitled')

        self.logger.debug(f"Preview requested for url={url}")

        use_webview = settings_manager.get('preview_in_webview', True)

        if use_webview:
            PreviewWindow(self.root, url, title, self.ui_call)
        else:
            self._open_url_in_browser(url)

    def _open_selected_in_browser(self):
        """Context menu action to open the selected video in the browser."""
        video = self.tab_manager.get_selected_video()
        if not video:
            return

        platform = video.get('platform', 'YouTube')
        url = video.get('webpage_url')
        if not url:
            if platform == 'YouTube':
                video_id = video.get('video_id')
                url = f'https://www.youtube.com/watch?v={video_id}'
            else:
                return

        self._open_url_in_browser(url)

    def _open_url_in_browser(self, url: str):
        """Opens a given URL in the default system browser."""
        try:
            self.logger.debug(f"Opening URL in browser: {url}")
            webbrowser.open(url)
        except Exception as e:
            self.logger.error(f"Failed to open URL in browser: {e}")
            messagebox.showerror("Error", f"Could not open URL in browser:\n{e}")

    def _copy_selected_url(self):
        """Context menu action to copy the selected video's URL."""
        video = self.tab_manager.get_selected_video()
        if not video:
            return

        platform = video.get('platform', 'YouTube')
        url = video.get('webpage_url')
        if not url:
            if platform == 'YouTube':
                video_id = video.get('video_id')
                url = f'https://www.youtube.com/watch?v={video_id}'
            else:
                self.root.clipboard_clear()
                self.root.clipboard_append("No URL available")
                show_toast(self.root, "No URL available for this item.")
                return

        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        show_toast(self.root, "URL copied to clipboard!")

    def _download_video(self):
        video = self.tab_manager.get_selected_video()
        if not video:
            messagebox.showinfo('Download', 'Please select a video first.')
            return
        try:
            platform = video.get('platform', 'YouTube')
            title = video.get('title', 'Unknown')
            query = self.query_entry.get().strip() or "default"
            output_path = self.media_processor.get_output_path(query)

            def on_complete(success):
                if success:
                    try:
                        os.startfile(str(output_path))
                        clean_title = title.replace('🟢 ','').replace('🔴 ','').strip()
                        caption, hashtags = VideoAnalyzer.generate_caption_and_hashtags(clean_title)
                        CaptionDialog(self.root, clean_title, caption, hashtags, str(output_path))
                    except Exception as e:
                        self.logger.error(f'Post-download caption error: {e}')
                else:
                    messagebox.showerror('Download Error', f'Failed to download "{title[:40]}...". Check logs.')

            if platform == 'Facebook':
                url = video.get('webpage_url')
                cookies_path = self.facebook_cookies_path_var.get() if self.use_facebook_cookies_var.get() else None
                self._execute_download(
                    download_func=download_facebook_video,
                    on_complete=on_complete,
                    title=title,
                    url=url,
                    cookies_path=cookies_path,
                    output_path=output_path
                )
            else: # YouTube
                video_id = video.get('video_id')
                url = f'https://www.youtube.com/watch?v={video_id}'
                self._execute_download(
                    download_func=self.media_processor.download_video,
                    on_complete=on_complete,
                    title=title,
                    video_id=video_id,
                    url=url,
                    output_path=output_path
                )

            messagebox.showinfo('Download', f'Download started for "{title[:30]}..."!')

        except Exception as e:
            self.logger.error(f'Download error: {e}')
            messagebox.showerror('Download Error', f'Error preparing download: {e}')

    def _execute_download(self, download_func: Callable, on_complete: Callable, title: str, **kwargs):
        """Executes a download function in a thread and calls back on completion."""
        def _task():
            try:
                success = download_func(**kwargs)
                self.ui_call(on_complete, success)
            except Exception as e:
                self.logger.error(f"Exception during download execution for '{title}': {e}")
                self.ui_call(on_complete, False)

        threading.Thread(target=_task, daemon=True).start()

    def _transcribe_video(self):
        video = self.tab_manager.get_selected_video()
        if not video:
            messagebox.showinfo('Transcribe', 'Please select a video first.')
            return
        try:
            video_id = video.get('video_id')
            title = video.get('title', 'Unknown')
            url = f'https://www.youtube.com/watch?v={video_id}'
            progress = ProgressDialog(self.root, "Transcribing...")
            def progress_callback(status): progress.update_status(status)
            from config import AUDIO_CLIPS_PATH
            audio_path = self.media_processor.download_audio_only(video_id, url, AUDIO_CLIPS_PATH)
            if not audio_path:
                progress.close(); messagebox.showerror('Error', 'Failed to download audio'); return
            transcript = self.media_processor.transcribe_audio(audio_path, progress_callback)
            progress.close()
            if transcript:
                clean_title = title.replace('🟢 ','').replace('🔴 ','').strip()
                TranscriptDialog(self.root, clean_title, video_id, transcript, on_save_callback=self._load_winners_to_tab)
                try:
                    caption, hashtags = VideoAnalyzer.generate_caption_and_hashtags(clean_title, transcript)
                    CaptionDialog(self.root, clean_title, caption, hashtags, str(AUDIO_CLIPS_PATH))
                except Exception as e:
                    self.logger.error(f'Caption generation error: {e}')
            else:
                messagebox.showerror('Error', 'Failed to transcribe audio')
        except Exception as e:
            if 'progress' in locals(): progress.close()
            self.logger.error(f'Transcription error: {e}')
            messagebox.showerror('Transcription Error', f'Error: {e}')

    def _find_raw_source(self):
        video = self.tab_manager.get_selected_video()
        if not video:
            messagebox.showinfo('Find Raw', 'Please select a video first.')
            return
        try:
            video_id = video.get('video_id')
            url = f'https://www.youtube.com/watch?v={video_id}'
            query = self.query_entry.get().strip() or "default"
            base_path = self.media_processor.get_output_path(query)
            progress = ProgressDialog(self.root, "Processing Video...")
            def progress_callback(status): progress.update_status(status)
            results = self.media_processor.process_video_for_analysis(
                video_id, url, base_path, progress_callback
            )
            progress.close()
            if results['success']:
                output_dir = base_path / video_id
                try: os.startfile(str(output_dir))
                except Exception: pass
                messagebox.showinfo(
                    'Find Raw',
                    'Frames & audio extracted.\nOpen the folder and drop a few clear frames into Google Lens/Bing/Yandex, or fingerprint the audio.\n\n'
                    f'Folder:\n{output_dir}'
                )
            else:
                messagebox.showerror('Error', 'Failed to process video')
        except Exception as e:
            if 'progress' in locals(): progress.close()
            self.logger.error(f'Raw source error: {e}')
            messagebox.showerror('Error', f'Error: {e}')

    def _open_clip_folder(self):
        try:
            desktop = Path.home() / 'Desktop'
            os.startfile(str(desktop))
        except Exception as e:
            messagebox.showerror('Error', f'Could not open folder:\n{e}')

    def _set_timer(self):
        time_str = simpledialog.askstring('Set Hustle Timer', 'Enter end time (e.g., 15:00 for 3:00 PM):')
        if not time_str: return
        try:
            hours, minutes = map(int, time_str.split(':'))
            now = datetime.now()
            target = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if target < now: target += timedelta(days=1)
            self.timer_widget.set_timer(target)
        except Exception:
            messagebox.showerror('Timer Error', 'Invalid time format. Use HH:MM (24-hour format).')

    def _load_selected_transcripts(self):
        active_tab = self.tab_manager.get_active_tab()
        if not active_tab or not active_tab.is_winners_tab:
            messagebox.showinfo("Info", "This action is only available in the Library tab.", parent=self.root)
            return

        selected_items = active_tab.tree.selection()
        if not selected_items:
            messagebox.showinfo("Info", "Please select one or more items from the library.", parent=self.root)
            return

        video_ids = [active_tab.tree.set(item, 'video_id') for item in selected_items]
        self.load_transcripts_into_prompt(video_ids)

    def load_transcripts_into_prompt(self, video_ids: list[str]):
        tm = TranscriptsManager()
        combined_text = tm.combine_text(video_ids)

        if not combined_text:
            messagebox.showinfo("Not Found", "No transcripts were found for the selected videos.", parent=self.root)
            return

        # This is a simplified way to open the prompt builder.
        # In a real app, you might want to pass the text to an existing instance.
        # Here, we open a new dialog with the combined text.
        # We need a representative title and video_id for the dialog constructor.
        first_video_id = video_ids[0]
        first_video_data = self.winners_manager.get_winner_by_id(first_video_id)
        title = f"Combined {len(video_ids)} transcripts"
        if first_video_data:
            title = first_video_data.display_title or first_video_data.title

        TranscriptDialog(self.root, title, first_video_id, combined_text, on_save_callback=self._load_winners_to_tab)


    def open_transcript_for_selected(self):
        video = self.tab_manager.get_selected_video()
        if not video:
            return

        video_id = video.get('video_id')
        tm = TranscriptsManager()
        transcript_data = tm.load(video_id)

        if transcript_data:
            TranscriptDialog(self.root, transcript_data.get('title', ''), video_id, transcript_data.get('text', ''), on_save_callback=self._load_winners_to_tab)
        else:
            messagebox.showinfo("Not Found", "No transcript found for this video.", parent=self.root)

    def delete_transcript_for_selected(self):
        video = self.tab_manager.get_selected_video()
        if not video:
            return

        video_id = video.get('video_id')
        video_title = video.get('title', 'this video')

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the transcript for '{video_title}'?", parent=self.root):
            tm = TranscriptsManager()
            if tm.delete(video_id):
                self._load_winners_to_tab() # Refresh the view
                show_toast(self.root, "Transcript deleted.")
            else:
                messagebox.showerror("Error", "Failed to delete transcript.", parent=self.root)

    def load_transcript_for_selected(self):
        video = self.tab_manager.get_selected_video()
        if not video:
            return
        self.load_transcripts_into_prompt([video.get('video_id')])

    def _download_transcript_async(self, video_id: str, callback: Optional[callable] = None):
        """Downloads a transcript in a background thread."""
        self.logger.info(f"Starting async transcript download for {video_id}")

        def _task():
            try:
                url = f'https://www.youtube.com/watch?v={video_id}'
                audio_path = self.media_processor.download_audio_only(video_id, url, AUDIO_CLIPS_PATH)
                if not audio_path:
                    self.logger.error(f"Failed to download audio for {video_id}")
                    return

                self.media_processor.transcribe_audio(audio_path)
                self.logger.info(f"Successfully transcribed {video_id}")

                if callback:
                    self.ui_call(callback)
            except Exception as e:
                self.logger.error(f"Async transcription failed for {video_id}: {e}")

        threading.Thread(target=_task, daemon=True).start()

    def _open_prompt_builder(self, video_id: str, title: str):
        """Opens the transcript dialog for a given video."""
        transcript_path = AUDIO_CLIPS_PATH / f"{video_id}_transcript.txt"
        if not transcript_path.exists():
            messagebox.showwarning("Transcript Not Found", "The transcript for this video is not available yet. Please wait for the download to complete.", parent=self.root)
            return

        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_content = f.read()

            TranscriptDialog(self.root, title, video_id, transcript_content, on_save_callback=self._load_winners_to_tab)
        except Exception as e:
            self.logger.error(f"Failed to open prompt builder for {video_id}: {e}")
            messagebox.showerror("Error", f"Could not open transcript file: {e}", parent=self.root)

    def _on_winner_select(self, event=None):
        video = self.tab_manager.get_selected_video()
        is_manual = video and video.get('video_id', '').startswith('manual_')

        buttons_to_disable = ["Preview", "Download", "Transcribe", "Find Raw"]
        for button_text in buttons_to_disable:
            if button_text in self.action_buttons:
                state = "disabled" if is_manual else "normal"
                self.action_buttons[button_text].config(state=state)

    def _add_manual_transcript(self):
        dialog = ManualTranscriptDialog(self.root, self.winners_manager)
        if dialog.result:
            data = dialog.result
            video_id = f"manual_{uuid.uuid4()}"

            # Create a dummy winner object
            winner_data = {
                "video_id": video_id,
                "title": data["title"],
                "display_title": data["title"],
                "notes": data["notes"],
                "tags": data["tags"],
                "folder": data["folder"],
                "has_transcript": True,
                # Add default values for other required fields
                "viral_score": 0.0,
                "views": 0,
                "likes": 0,
                "ratio": 0.0,
                "vph": 0.0,
                "duration": "00:00:00",
                "age": "",
                "repost_flag": False,
                "repost_reason": "",
            }
            self.winners_manager.add_winner(winner_data, data["folder"], notes=data["notes"])

            # Create and save the transcript record
            transcript_record = {
                "video_id": video_id,
                "title": data["title"],
                "source_url": "",
                "channel_title": "Manual Entry",
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "language": "en",
                "duration": "00:00:00",
                "tags": data["tags"],
                "folder": data["folder"],
                "notes": data["notes"],
                "text": data["text"],
            }
            self.transcripts_manager.save(transcript_record)

            # Refresh the library view
            self._load_winners_to_tab()

    def _delete_selected_winners(self):
        active_tab = self.tab_manager.get_active_tab()
        if not active_tab or not active_tab.is_winners_tab:
            return

        selected_items = active_tab.tree.selection()
        if not selected_items:
            messagebox.showinfo("Delete", "No items selected.", parent=self.root)
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {len(selected_items)} selected item(s)?\n"
            "This will delete both the library entry and any associated transcript files.",
            parent=self.root
        )

        if confirm:
            deleted_count = 0
            for item in selected_items:
                video_id = active_tab.tree.set(item, 'video_id')
                if video_id:
                    if self.winners_manager.remove_winner(video_id):
                        self.transcripts_manager.delete(video_id)
                        deleted_count += 1

            if deleted_count > 0:
                show_toast(self.root, f"{deleted_count} item(s) deleted.")
                self._load_winners_to_tab()

    def _manage_folders(self):
        FolderManagerDialog(self.root, self.winners_manager)
        self.tab_manager.update_folder_filter()

    def _show_facebook_error_modal(self, url: str):
        """Shows a friendly modal when Facebook extraction fails definitively."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Facebook Extraction Failed")
        dialog.geometry("450x200")
        dialog.configure(bg=COLORS.get('bg_primary'))
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = tk.Frame(dialog, bg=COLORS.get('bg_primary'), padx=15, pady=15)
        main_frame.pack(fill='both', expand=True)

        tk.Label(main_frame, text="Facebook changed their API and yt-dlp hasn't shipped a fix yet.",
                  fg=COLORS.get('fg_primary'), bg=COLORS.get('bg_primary')).pack(pady=5)

        version = settings_manager.get('yt_dlp_current_version', 'N/A')
        last_update = settings_manager.get('yt_dlp_last_update_check', 'Never')
        if last_update != 'Never':
            try:
                last_update = datetime.fromisoformat(last_update).strftime('%Y-%m-%d %H:%M')
            except:
                pass # keep as is

        tk.Label(main_frame, text=f"yt-dlp version: {version} (Last check: {last_update})",
                  fg=COLORS.get('fg_secondary'), bg=COLORS.get('bg_primary')).pack(pady=5)

        button_frame = tk.Frame(main_frame, bg=COLORS.get('bg_primary'))
        button_frame.pack(pady=15)

        def _open_and_close():
            webbrowser.open(url)
            dialog.destroy()

        def _update_and_close():
            self._perform_facebook_analysis(url) # Re-trigger the whole flow
            dialog.destroy()

        def _learn_more():
            webbrowser.open("https://github.com/yt-dlp/yt-dlp/issues?q=is%3Aissue+is%3Aopen+facebook")
            dialog.destroy()

        ttk.Button(button_frame, text="Open in Browser", command=_open_and_close).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Update yt-dlp & Retry", command=_update_and_close).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Learn More", command=_learn_more).pack(side='left', padx=5)


class FacebookAnalysisTask:
    """
    Manages the complex, multi-step process of analyzing a Facebook URL,
    including retries, updates, and user prompts.
    """
    def __init__(self, main_window: 'MainWindow', url: str):
        self.main = main_window
        self.logger = main_window.logger
        self.original_url = url
        self.tab_id = main_window.tab_manager.get_active_tab_id()

    def run(self):
        """Executes the analysis task. Designed to be run in a thread."""
        self.logger.info(f"Starting Facebook analysis for URL: {self.original_url}")

        # Attempt 1: Try the original URL
        result = self._try_extraction(self.original_url)

        if result.success:
            self.logger.debug("FB analysis completed in worker; dispatching to UI thread")
            self.main.ui_call(self.main._finish_facebook_analysis, result.data)
            return

        # Check for specific extractor errors
        is_extractor_error = "extractorerror" in result.error.lower() or "cannot parse data" in result.error.lower()

        if is_extractor_error:
            self.logger.warning(f"FB extractor error detected: {result.error[:100]}")

            # Attempt 2: Try canonical URLs
            canonical_url = canonicalize_facebook_url(self.original_url)
            if canonical_url and canonical_url != self.original_url:
                self.logger.info(f"Retrying with canonical URL: {canonical_url}")
                result = self._try_extraction(canonical_url)
                if result.success:
                    self.main.ui_call(self.main._finish_facebook_analysis, result.data)
                    return

            # Attempt 3: Auto-update yt-dlp and retry
            if settings_manager.get('yt_dlp_auto_update', True) and not self.main.yt_dlp_updated_this_session:
                self.main.yt_dlp_updated_this_session = True # Prevent multiple updates
                self.logger.info("Attempting yt-dlp self-update...")
                self.main.progress_dialog.update_status("FB extractor error, updating yt-dlp...")

                update_result = update_yt_dlp()
                self.logger.info(f"yt-dlp update result: success={update_result.success}, updated={update_result.updated}, msg={update_result.message}")

                if update_result.success and update_result.updated:
                    self.logger.info("Retrying FB extraction after update...")
                    self.main.ui_call(self.main.progress_dialog.update_status, "Update complete, retrying extraction...")
                    result = self._try_extraction(canonical_url or self.original_url)
                    if result.success:
                        self.main.ui_call(self.main._finish_facebook_analysis, result.data)
                        return

        # If all else fails, check for login error and prompt or show final error modal
        is_login_error = "login required" in result.error.lower() or "you must log in" in result.error.lower()
        if is_login_error:
            self.logger.info("Login error detected, prompting user for cookies.")
            self.main.ui_call(self._prompt_for_cookies)
        else:
            self.logger.error(f"All FB extraction attempts failed. Final error: {result.error}")
            self.main.ui_call(self.main._show_facebook_error_modal, self.original_url)
            # Also update the main UI to show a generic failure
            self.main.ui_call(self.main._finish_facebook_analysis, {'error': 'final_failure'})


    def _try_extraction(self, url: str, use_cookies: bool = False) -> 'ExtractionResult':
        """A single attempt to extract metadata for a given URL."""
        cookies_path = self.main.facebook_cookies_path_var.get() if use_cookies else None
        extra_args = ["--extractor-args", "facebook:lang=en_US"]
        return run_metadata_dump(url, cookies=cookies_path, extra_args=extra_args)

    def _prompt_for_cookies(self):
        """Show a messagebox on the main thread to ask about using cookies."""
        should_retry = messagebox.askyesno(
            "Login Required",
            "This video seems to be private or requires a login.\n\n"
            "Would you like to retry using your Facebook cookies.txt file?",
            parent=self.main.root
        )
        if should_retry:
            self.logger.info("User opted to retry with cookies.")
            # This needs to run in a new thread
            threading.Thread(target=self._retry_with_cookies, daemon=True).start()
        else:
             self.main.ui_call(self.main._finish_facebook_analysis, {'error': 'user_declined_cookies'})


    def _retry_with_cookies(self):
        """Final attempt to extract metadata using cookies."""
        url_to_try = canonicalize_facebook_url(self.original_url) or self.original_url
        result = self._try_extraction(url_to_try, use_cookies=True)
        if result.success:
            self.main.ui_call(self.main._finish_facebook_analysis, result.data)
        else:
            self.logger.error(f"FB extraction with cookies failed. Final error: {result.error}")
            self.main.ui_call(self.main._show_facebook_error_modal, self.original_url)
            self.main.ui_call(self.main._finish_facebook_analysis, {'error': 'cookie_failure'})
