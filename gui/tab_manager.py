"""
Tab management system for multiple search sessions
"""

import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Dict, Optional, List
from dataclasses import dataclass
from config import COLORS
from gui.components import Tooltip, bind_tooltip, sort_treeview_column


@dataclass
class TabData:
    """Data structure for tab information"""
    tab_id: str
    frame: tk.Frame
    label: tk.Label
    status_label: Optional[tk.Label]
    close_button: Optional[tk.Button]
    tree: ttk.Treeview
    search_term: str
    results: List[Dict]
    status_text: str
    tooltip_data: Dict[str, str]
    is_winners_tab: bool = False
    # Optional fields for library tab
    container: Optional[tk.Frame] = None
    folder_filter_combo: Optional[ttk.Combobox] = None


def _format_percentage(value: Optional[float], decimals: int = 1) -> str:
    """Format a float ratio (e.g., 0.041) as a percentage string (e.g., '4.1%')."""
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except Exception:
        return "-"


def _percent_to_float(txt: str) -> float:
    """Convert '4.1%' -> 0.041 for numeric sorting (returns -1.0 on failure)."""
    try:
        return float(str(txt).strip().replace('%', '')) / 100.0
    except Exception:
        return -1.0


def _duration_to_seconds(txt: str) -> int:
    """
    Parse duration strings like '01:23:45', '12:34', '45' to total seconds.
    Returns -1 on failure so blanks sink to the bottom.
    """
    if not txt:
        return -1
    s = str(txt).strip()
    try:
        parts = s.split(':')
        parts = [p.strip() for p in parts]
        if len(parts) == 3:
            h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
            return h * 3600 + m * 60 + sec
        elif len(parts) == 2:
            m, sec = int(parts[0]), int(parts[1])
            return m * 60 + sec
        elif len(parts) == 1 and parts[0].isdigit():
            return int(parts[0])
        else:
            return -1
    except Exception:
        return -1


# Regex for age tokens like "1y", "2yr", "3 years", "4mo", "5w", "6d", "7h", "30m", "45s"
_AGE_TOKEN_RE = re.compile(
    r'(\d+)\s*(years?|yrs?|y|months?|mos?|mo|weeks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)',
    re.IGNORECASE
)

_AGE_UNIT_SECONDS = {
    'y': 365 * 24 * 3600,
    'yr': 365 * 24 * 3600,
    'year': 365 * 24 * 3600,
    'years': 365 * 24 * 3600,
    'mo': 30 * 24 * 3600,
    'mos': 30 * 24 * 3600,
    'month': 30 * 24 * 3600,
    'months': 30 * 24 * 3600,
    'w': 7 * 24 * 3600,
    'week': 7 * 24 * 3600,
    'weeks': 7 * 24 * 3600,
    'd': 24 * 3600,
    'day': 24 * 3600,
    'days': 24 * 3600,
    'h': 3600,
    'hr': 3600,
    'hrs': 3600,
    'hour': 3600,
    'hours': 3600,
    'm': 60,
    'min': 60,
    'mins': 60,
    'minute': 60,
    'minutes': 60,
    's': 1,
    'sec': 1,
    'secs': 1,
    'second': 1,
    'seconds': 1,
}


def _age_to_seconds(txt: str) -> int:
    """
    Parse age strings like '1y 2mo', '3w', '4d', '5h 30m', '12h', '45m', '30s', with/without 'ago'.
    Returns seconds (older -> larger number). Returns -1 on failure.
    """
    if not txt:
        return -1
    s = str(txt).strip().lower().replace('ago', '').strip()
    total = 0
    found = False
    for amount, unit in _AGE_TOKEN_RE.findall(s):
        found = True
        amt = int(amount)
        u = unit.lower()
        # normalize unit to our keys
        if u in ('yr', 'yrs', 'year', 'years', 'y'):
            key = 'year' if u.startswith('year') else 'y'
        elif u in ('month', 'months', 'mo', 'mos'):
            key = 'month' if u.startswith('month') else 'mo'
        elif u in ('week', 'weeks', 'w'):
            key = 'week' if u.startswith('week') else 'w'
        elif u in ('day', 'days', 'd'):
            key = 'day' if u.startswith('day') else 'd'
        elif u in ('hour', 'hours', 'hr', 'hrs', 'h'):
            key = 'hour' if u.startswith('hour') else ('hr' if u.startswith('hr') else 'h')
        elif u in ('minute', 'minutes', 'min', 'mins', 'm'):
            key = 'minute' if u.startswith('minu') else ('min' if u.startswith('min') else 'm')
        elif u in ('second', 'seconds', 'sec', 'secs', 's'):
            key = 'second' if u.startswith('sec') is False and u.startswith('second') else ('sec' if u.startswith('sec') else 's')
        else:
            key = u
        # Map a few normalized keys to exact dictionary entries
        alias_map = {
            'year': 'years',
            'month': 'months',
            'week': 'weeks',
            'day': 'days',
            'hour': 'hours',
            'minute': 'minutes',
            'second': 'seconds',
            'hr': 'hrs'
        }
        key = alias_map.get(key, key)
        seconds = _AGE_UNIT_SECONDS.get(key, _AGE_UNIT_SECONDS.get(u, 0))
        total += amt * seconds
    return total if found else -1


from data.winners_manager import WinnersManager
from data.transcripts_manager import TranscriptsManager

class TabManager:
    """Manages multiple search tabs"""

    def __init__(self, main_window, parent: tk.Widget, tree_container: tk.Widget, winners_manager: WinnersManager, on_tab_switch: callable = None):
        self.main_window = main_window
        self.parent = parent
        self.tree_container = tree_container
        self.winners_manager = winners_manager
        self.on_tab_switch = on_tab_switch
        self.tabs: Dict[str, TabData] = {}
        self.active_tab_id: Optional[str] = None
        self.tab_counter = 0
        self.tooltip = Tooltip()
        self.winners_tab_id: Optional[str] = None

        self._create_tab_container()

    def _create_tab_container(self):
        """Create the scrollable tab container"""
        self.tabs_frame = tk.Frame(self.parent, bg=COLORS['bg_primary'], height=50)
        self.tabs_frame.pack(fill='x', padx=5, pady=(5, 0))
        self.tabs_frame.pack_propagate(False)

        self.tabs_canvas = tk.Canvas(
            self.tabs_frame,
            bg=COLORS['bg_primary'],
            height=40,
            highlightthickness=0
        )

        self.tabs_scrollbar = ttk.Scrollbar(
            self.tabs_frame,
            orient="horizontal",
            command=self.tabs_canvas.xview
        )

        self.tabs_canvas.configure(xscrollcommand=self.tabs_scrollbar.set)

        self.tabs_container = tk.Frame(self.tabs_canvas, bg=COLORS['bg_primary'])
        self.tabs_canvas.create_window((0, 0), window=self.tabs_container, anchor="nw")

        self.tabs_canvas.pack(side="top", fill="both", expand=True)
        self.tabs_scrollbar.pack(side="bottom", fill="x")

        def on_mousewheel(event):
            self.tabs_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        self.tabs_canvas.bind("<MouseWheel>", on_mousewheel)

        self._create_new_tab_button()

    def _create_new_tab_button(self):
        new_tab_button = tk.Button(
            self.tabs_container,
            text="⊕",
            bg='#666666',
            fg=COLORS['fg_primary'],
            font=('Arial', 12, 'bold'),
            bd=1,
            padx=8,
            pady=8,
            command=self._add_new_tab_from_button
        )
        new_tab_button.pack(side='right', padx=5, pady=5)

    def _add_new_tab_from_button(self):
        self.add_new_tab()
        self._update_canvas_scroll()

    def _update_canvas_scroll(self):
        self.tabs_container.update_idletasks()
        self.tabs_canvas.configure(scrollregion=self.tabs_canvas.bbox("all"))

    def _generate_tab_id(self) -> str:
        self.tab_counter += 1
        return f"tab_{self.tab_counter}"

    def create_winners_tab(self) -> str:
        if self.winners_tab_id:
            return self.winners_tab_id

        tab_id = "winners_tab"
        display_name = "Library"

        tab_frame = tk.Frame(self.tabs_container, bg='#FFD700', relief='solid', bd=2, width=120, height=40)
        tab_frame.pack_propagate(False)

        tab_label = tk.Label(
            tab_frame, text=display_name, bg='#FFD700', fg='#000000',
            font=('Segoe UI', 11, 'bold')
        )
        tab_label.pack(fill='both', expand=True)

        close_button = None
        library_container = tk.Frame(self.tree_container, bg=COLORS.get('bg_primary'))

        filter_frame = tk.Frame(library_container, bg=COLORS.get('bg_primary'))
        filter_frame.pack(fill='x', pady=5, padx=5)

        tk.Label(filter_frame, text="Filter by Folder:", bg=COLORS.get('bg_primary'), fg=COLORS.get('fg_primary')).pack(side='left')

        folder_var = tk.StringVar()
        folder_filter_combo = ttk.Combobox(filter_frame, textvariable=folder_var, state='readonly', width=30)
        folder_filter_combo.pack(side='left', padx=5)

        add_button = ttk.Button(filter_frame, text="Add Manual Transcript", command=self.main_window._add_manual_transcript)
        add_button.pack(side='right', padx=5)

        delete_button = ttk.Button(filter_frame, text="Delete Selected", command=self.main_window._delete_selected_winners)
        delete_button.pack(side='right', padx=5)

        manage_button = ttk.Button(filter_frame, text="Manage Folders", command=self.main_window._manage_folders)
        manage_button.pack(side='right', padx=5)

        tree = self._create_winners_treeview(library_container)
        tree.pack(side='bottom', fill='both', expand=True)

        self._bind_winners_tab_events(tab_frame, tab_label, tab_id)

        tab_data = TabData(
            tab_id=tab_id, frame=tab_frame, label=tab_label, status_label=None,
            close_button=close_button, tree=tree, search_term="Library",
            results=[], status_text='idle', tooltip_data={}, is_winners_tab=True,
            container=library_container, folder_filter_combo=folder_filter_combo
        )

        self.tabs[tab_id] = tab_data
        self.winners_tab_id = tab_id
        self._bind_tree_tooltip(tree, tab_id)
        tab_frame.pack(side='left', fill='y', padx=2, pady=2)

        folder_filter_combo.bind("<<ComboboxSelected>>", lambda event: self.filter_library_by_folder())

        return tab_id

    def add_new_tab(self, search_term: str = "") -> str:
        tab_id = self._generate_tab_id()
        display_name = search_term if search_term else "New Search"

        tab_frame = tk.Frame(self.tabs_container, bg=COLORS['bg_tertiary'], relief='solid', bd=1)

        tab_label = tk.Label(
            tab_frame,
            text=display_name[:20] + "..." if len(display_name) > 20 else display_name,
            bg=COLORS['bg_tertiary'], fg=COLORS['fg_secondary'],
            font=('Segoe UI', 9), padx=12, pady=8
        )
        tab_label.pack(side='left')

        status_label = tk.Label(
            tab_frame, text="", bg=COLORS['bg_tertiary'], fg=COLORS['fg_success'],
            font=('Segoe UI', 8, 'bold'), padx=4
        )
        status_label.pack(side='left')

        close_button = tk.Button(
            tab_frame, text="×", bg=COLORS['bg_tertiary'], fg=COLORS['fg_secondary'],
            font=('Arial', 12, 'bold'), bd=0, padx=8, pady=2,
            activebackground=COLORS['fg_error'], activeforeground=COLORS['fg_primary'],
            command=lambda: self.close_tab(tab_id)
        )
        close_button.pack(side='right')

        tree = self._create_tab_treeview()
        self._bind_tab_events(tab_frame, tab_label, status_label, close_button, tab_id)

        tab_data = TabData(
            tab_id=tab_id, frame=tab_frame, label=tab_label, status_label=status_label,
            close_button=close_button, tree=tree, search_term=search_term,
            results=[], status_text='idle', tooltip_data={}, is_winners_tab=False
        )
        self.tabs[tab_id] = tab_data
        self._bind_tree_tooltip(tree, tab_id)
        tab_frame.pack(side='left', fill='y', padx=2, pady=2)
        self.switch_to_tab(tab_id)
        return tab_id

    def _create_tab_treeview(self) -> ttk.Treeview:
        columns = ('Engine', 'Title', 'Score', 'Views', 'Likes', 'L/V Ratio', 'VPH', 'Duration', 'Age', 'video_id')
        display_columns = ('Engine', 'Title', 'Score', 'Views', 'Likes', 'L/V Ratio', 'VPH', 'Duration', 'Age')

        tree = ttk.Treeview(self.parent, columns=columns, show='headings', displaycolumns=display_columns)

        column_widths = {
            'Engine': 40, 'Title': 300, 'Score': 80, 'Views': 80, 'Likes': 80,
            'L/V Ratio': 80, 'VPH': 80, 'Duration': 80, 'Age': 80
        }

        sort_states = {}

        def toggle_sort(column):
            current_state = sort_states.get(column, False)
            new_state = not current_state
            sort_states[column] = new_state
            for col in display_columns:
                if col != column:
                    sort_states[col] = False

            if column == 'L/V Ratio':
                items = [(_percent_to_float(tree.set(iid, column)), iid) for iid in tree.get_children("")]
            elif column == 'Duration':
                items = [(_duration_to_seconds(tree.set(iid, column)), iid) for iid in tree.get_children("")]
            elif column == 'Age':
                items = [(_age_to_seconds(tree.set(iid, column)), iid) for iid in tree.get_children("")]
            else:
                items = None

            if items is not None:
                items.sort(key=lambda x: x[0], reverse=new_state)
                for idx, (_, iid) in enumerate(items):
                    tree.move(iid, "", idx)
            else:
                sort_treeview_column(tree, column, new_state)

        for col in display_columns:
            tree.heading(col, text=col, command=lambda c=col: toggle_sort(c))
            tree.column(col, anchor='center', width=column_widths[col])

        tree.column('video_id', width=0, stretch=False)
        tree.bind("<Double-1>", self.main_window._on_row_double_click)

        # Context Menu for search results
        context_menu = tk.Menu(tree, tearoff=0)
        context_menu.add_command(label="Preview", command=self.main_window._on_row_double_click)
        context_menu.add_command(label="Open in Browser", command=lambda: self.main_window._open_selected_in_browser())
        context_menu.add_command(label="Copy URL", command=lambda: self.main_window._copy_selected_url())

        def show_context_menu(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                context_menu.post(event.x_root, event.y_root)

        tree.bind("<Button-3>", show_context_menu)
        return tree

    def _create_winners_treeview(self, parent_container: tk.Widget) -> ttk.Treeview:
        columns = ('Transcript', 'Title', 'Score', 'Views', 'Likes', 'L/V Ratio', 'VPH', 'Duration', 'Date Saved', 'Folder', 'video_id')
        display_columns = ('Transcript', 'Title', 'Score', 'Views', 'Likes', 'L/V Ratio', 'VPH', 'Duration', 'Date Saved', 'Folder')

        tree = ttk.Treeview(parent_container, columns=columns, show='headings', displaycolumns=display_columns)

        column_widths = {
            'Transcript': 40, 'Title': 250, 'Score': 70, 'Views': 70, 'Likes': 70,
            'L/V Ratio': 70, 'VPH': 70, 'Duration': 70, 'Date Saved': 120, 'Folder': 80
        }

        sort_states = {}

        def toggle_sort(column):
            current_state = sort_states.get(column, False)
            new_state = not current_state
            sort_states[column] = new_state
            for col in display_columns:
                if col != column:
                    sort_states[col] = False

            if column == 'L/V Ratio':
                items = [(_percent_to_float(tree.set(iid, column)), iid) for iid in tree.get_children("")]
            elif column == 'Duration':
                items = [(_duration_to_seconds(tree.set(iid, column)), iid) for iid in tree.get_children("")]
            else:
                items = None

            if items is not None:
                items.sort(key=lambda x: x[0], reverse=new_state)
                for idx, (_, iid) in enumerate(items):
                    tree.move(iid, "", idx)
            else:
                sort_treeview_column(tree, column, new_state)

        for col in display_columns:
            tree.heading(col, text=col, command=lambda c=col: toggle_sort(c))
            tree.column(col, anchor='center', width=column_widths[col])

        tree.column('video_id', width=0, stretch=False)

        # Context Menu
        context_menu = tk.Menu(tree, tearoff=0)
        context_menu.add_command(label="Preview Video", command=self.main_window._on_row_double_click)
        context_menu.add_separator()
        context_menu.add_command(label="Open Transcript", command=self.main_window.open_transcript_for_selected)
        context_menu.add_command(label="Delete Transcript", command=self.main_window.delete_transcript_for_selected)
        context_menu.add_separator()
        context_menu.add_command(label="Load Transcript into Prompt Builder", command=self.main_window.load_transcript_for_selected)

        def show_context_menu(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                context_menu.post(event.x_root, event.y_root)

        tree.bind("<Button-3>", show_context_menu)
        tree.bind("<<TreeviewSelect>>", self.main_window._on_winner_select)
        tree.bind("<Double-1>", self.main_window._on_row_double_click)
        return tree

    def _bind_tab_events(self, tab_frame: tk.Frame, tab_label: tk.Label,
                         status_label: tk.Label, close_button: tk.Button, tab_id: str):
        def on_tab_click(event=None):
            self.switch_to_tab(tab_id)

        def on_tab_enter(event):
            if self.active_tab_id != tab_id:
                tab_frame.config(bg='#4a4a4a')
                tab_label.config(bg='#4a4a4a', fg=COLORS['fg_primary'])
                status_label.config(bg='#4a4a4a')

        def on_tab_leave(event):
            if self.active_tab_id != tab_id:
                tab_frame.config(bg=COLORS['bg_tertiary'])
                tab_label.config(bg=COLORS['bg_tertiary'], fg=COLORS['fg_secondary'])
                status_label.config(bg=COLORS['bg_tertiary'])

        def on_close_enter(event):
            close_button.config(bg=COLORS['fg_error'], fg=COLORS['fg_primary'])

        def on_close_leave(event):
            if self.tabs[tab_id].frame['bg'] == COLORS['bg_accent']:
                close_button.config(bg=COLORS['bg_accent'], fg=COLORS['fg_primary'])
            else:
                close_button.config(bg=COLORS['bg_tertiary'], fg=COLORS['fg_secondary'])

        tab_label.bind("<Button-1>", on_tab_click)
        tab_frame.bind("<Button-1>", on_tab_click)
        tab_label.bind("<Enter>", on_tab_enter)
        tab_label.bind("<Leave>", on_tab_leave)
        tab_frame.bind("<Enter>", on_tab_enter)
        tab_frame.bind("<Leave>", on_tab_leave)
        close_button.bind("<Enter>", on_close_enter)
        close_button.bind("<Leave>", on_close_leave)

    def _bind_winners_tab_events(self, tab_frame: tk.Frame, tab_label: tk.Label, tab_id: str):
        def on_tab_click(event=None):
            self.switch_to_tab(tab_id)

        def on_tab_enter(event):
            if self.active_tab_id != tab_id:
                tab_frame.config(bg='#FFF700')

        def on_tab_leave(event):
            if self.active_tab_id != tab_id:
                tab_frame.config(bg='#FFD700')

        tab_label.bind("<Button-1>", on_tab_click)
        tab_frame.bind("<Button-1>", on_tab_click)
        tab_label.bind("<Enter>", on_tab_enter)
        tab_label.bind("<Leave>", on_tab_leave)
        tab_frame.bind("<Enter>", on_tab_enter)
        tab_frame.bind("<Leave>", on_tab_leave)

    def _bind_tree_tooltip(self, tree: ttk.Treeview, tab_id: str):
        def get_tooltip_text(event):
            row_id = tree.identify_row(event.y)
            col = tree.identify_column(event.x)
            if row_id and col == '#1':  # Title column
                return self.tabs.get(tab_id, {}).tooltip_data.get(row_id, '')
            return ""
        bind_tooltip(tree, self.tooltip, get_tooltip_text)

    def close_tab(self, tab_id: str):
        if tab_id == self.winners_tab_id:
            return
        if len(self.tabs) <= 1:
            messagebox.showwarning("Cannot Close", "Cannot close the last tab!")
            return
        if tab_id in self.tabs:
            tab_data = self.tabs[tab_id]
            tab_data.frame.destroy()
            tab_data.tree.destroy()
            del self.tabs[tab_id]
            if self.active_tab_id == tab_id:
                if self.winners_tab_id and self.winners_tab_id in self.tabs:
                    self.switch_to_tab(self.winners_tab_id)
                else:
                    first_tab_id = next(iter(self.tabs.keys()))
                    self.switch_to_tab(first_tab_id)
            self._update_canvas_scroll()

    def switch_to_tab(self, tab_id: str):
        if tab_id not in self.tabs:
            return
        for _, tab_data in self.tabs.items():
            if tab_data.is_winners_tab and tab_data.container:
                tab_data.container.place_forget()
            else:
                tab_data.tree.place_forget()

            if tab_data.is_winners_tab:
                tab_data.frame.config(bg='#FFD700', relief='solid')
                tab_data.label.config(bg='#FFD700', fg='#000000')
                if tab_data.status_label:
                    tab_data.status_label.config(bg='#FFD700')
            else:
                tab_data.frame.config(bg=COLORS['bg_tertiary'], relief='solid')
                tab_data.label.config(bg=COLORS['bg_tertiary'], fg=COLORS['fg_secondary'])
                tab_data.status_label.config(bg=COLORS['bg_tertiary'])
                if tab_data.close_button:
                    tab_data.close_button.config(bg=COLORS['bg_tertiary'])

        active_tab = self.tabs[tab_id]
        if active_tab.is_winners_tab and active_tab.container:
            active_tab.container.place(in_=self.tree_container, x=0, y=0, relwidth=1, relheight=1)
            self.update_folder_filter()
        else:
            active_tab.tree.place(in_=self.tree_container, x=0, y=0, relwidth=1, relheight=1)

        if active_tab.is_winners_tab:
            active_tab.frame.config(bg='#FFB000', relief='raised')
            active_tab.label.config(bg='#FFB000', fg='#000000', font=('Segoe UI', 11, 'bold'))
            if active_tab.status_label:
                active_tab.status_label.config(bg='#FFB000')
        else:
            active_tab.frame.config(bg=COLORS['bg_accent'], relief='raised')
            active_tab.label.config(bg=COLORS['bg_accent'], fg=COLORS['fg_primary'], font=('Segoe UI', 9, 'bold'))
            active_tab.status_label.config(bg=COLORS['bg_accent'])
            if active_tab.close_button:
                active_tab.close_button.config(bg=COLORS['bg_accent'])

        self.active_tab_id = tab_id

        if self.on_tab_switch:
            self.on_tab_switch(active_tab)

    def update_tab_status(self, tab_id: str, status_text: str, status_type: str = 'idle'):
        if tab_id not in self.tabs:
            return
        tab_data = self.tabs[tab_id]
        if not tab_data.status_label:
            return

        tab_data.status_text = status_type

        colors = {
            'idle': '#000000' if tab_data.is_winners_tab else COLORS['fg_secondary'],
            'loading': '#000000' if tab_data.is_winners_tab else COLORS['fg_warning'],
            'complete': '#000000' if tab_data.is_winners_tab else COLORS['fg_success'],
            'error': '#FF0000' if tab_data.is_winners_tab else COLORS['fg_error']
        }
        icons = {'idle': '', 'loading': '⏳', 'complete': '✓', 'error': '❌'}

        display_text = f"{icons.get(status_type, '')} {status_text}".strip()
        tab_data.status_label.config(text=display_text, fg=colors.get(status_type, COLORS['fg_secondary']))

    def get_active_tab(self) -> Optional[TabData]:
        if self.active_tab_id and self.active_tab_id in self.tabs:
            return self.tabs[self.active_tab_id]
        return None

    def get_active_tab_id(self) -> Optional[str]:
        """Safely returns the ID of the currently active tab."""
        return self.active_tab_id

    def get_winners_tab(self) -> Optional[TabData]:
        if self.winners_tab_id and self.winners_tab_id in self.tabs:
            return self.tabs[self.winners_tab_id]
        return None

    def get_tab_count(self) -> int:
        return len(self.tabs)

    def clear_tab_results(self, tab_id: str):
        if tab_id in self.tabs:
            tab_data = self.tabs[tab_id]
            for item in tab_data.tree.get_children():
                tab_data.tree.delete(item)
            tab_data.results.clear()
            tab_data.tooltip_data.clear()

    def add_result_to_tab(self, tab_id: str, video_data: Dict):
        if tab_id not in self.tabs:
            return
        tab_data = self.tabs[tab_id]

        indicator = '🟢' if not video_data.get('repost_flag') else '🔴'
        title_display = f"{indicator} {video_data.get('title', '')}"
        score_display = video_data.get('viral_score', 'N/A')
        if score_display != 'N/A':
            score_display = f"{score_display:.3f}"

        ratio_display = _format_percentage(video_data.get('ratio'), 1)

        item_id = tab_data.tree.insert('', 'end', values=(
            video_data.get('engine', ''),
            title_display,
            score_display,
            video_data.get('views', 0),
            video_data.get('likes', 0),
            ratio_display,
            video_data.get('vph', 0),
            video_data.get('duration', '00:00'),
            video_data.get('age', ''),
            video_data.get('video_id', '')
        ))

        tab_data.tooltip_data[item_id] = video_data.get('repost_reason', '')
        tab_data.results.append(video_data)

    def add_winner_to_tab(self, winner_data: Dict):
        if not self.winners_tab_id or self.winners_tab_id not in self.tabs:
            return
        tab_data = self.tabs[self.winners_tab_id]

        indicator = '🟢' if not winner_data.get('repost_flag') else '🔴'

        # Use display_title if available, otherwise fallback to original title
        title_to_display = winner_data.get('display_title') or winner_data.get('title', '')
        title_display = f"{indicator} {title_to_display}"

        score_display = winner_data.get('viral_score', 'N/A')
        if score_display != 'N/A':
            score_display = f"{score_display:.3f}"

        ratio_display = _format_percentage(winner_data.get('ratio'), 1)

        tm = TranscriptsManager()
        has_transcript = tm.exists(winner_data.get('video_id', ''))
        transcript_icon = "📄" if has_transcript else ""

        item_id = tab_data.tree.insert('', 'end', values=(
            transcript_icon,
            title_display,
            score_display,
            winner_data.get('views', 0),
            winner_data.get('likes', 0),
            ratio_display,
            winner_data.get('vph', 0),
            winner_data.get('duration', '00:00'),
            winner_data.get('date_saved', ''),
            winner_data.get('folder', 'Default'),
            winner_data.get('video_id', '')
        ))

        tab_data.tooltip_data[item_id] = winner_data.get('repost_reason', '')
        tab_data.results.append(winner_data)

    def remove_winner_from_tab(self, video_id: str):
        if not self.winners_tab_id or self.winners_tab_id not in self.tabs:
            return
        tab_data = self.tabs[self.winners_tab_id]

        for item in tab_data.tree.get_children():
            if tab_data.tree.set(item, 'video_id') == video_id:
                tab_data.tree.delete(item)
                break

        tab_data.results = [r for r in tab_data.results if r.get('video_id') != video_id]

        tab_data.tooltip_data = {
            k: v for k, v in tab_data.tooltip_data.items()
            if k in [tab_data.tree.set(item, 'video_id') for item in tab_data.tree.get_children()]
        }

    def get_selected_video(self, tab_id: Optional[str] = None) -> Optional[Dict]:
        if tab_id is None:
            tab_id = self.active_tab_id
        if not tab_id or tab_id not in self.tabs:
            return None

        tab_data = self.tabs[tab_id]
        selection = tab_data.tree.selection()
        if not selection:
            return None

        video_id = tab_data.tree.set(selection[0], 'video_id')
        for video in tab_data.results:
            if video.get('video_id') == video_id:
                return video
        # Fallback for winners tab, which might have a filtered view
        if tab_data.is_winners_tab:
            winner = self.winners_manager.get_winner_by_id(video_id)
            if winner:
                return winner.to_dict()
        return None

    def update_video_data(self, video_id: str, new_data: dict):
        """Finds a video by its ID across all tabs and updates its data and UI."""
        for tab in self.tabs.values():
            for video in tab.results:
                if video.get('video_id') == video_id:
                    video.update(new_data)

                    # Update the UI Treeview
                    for item_id in tab.tree.get_children():
                        if tab.tree.set(item_id, 'video_id') == video_id:
                            if 'engine' in new_data:
                                tab.tree.set(item_id, 'Engine', new_data['engine'].upper())
                            # Add other UI updates here if needed in the future
                    return

    def update_folder_filter(self):
        """Updates the folder filter dropdown with the current folders."""
        winners_tab = self.get_winners_tab()
        if not winners_tab or not winners_tab.folder_filter_combo:
            return

        all_folders = ["All"] + self.winners_manager.get_all_folders()
        winners_tab.folder_filter_combo['values'] = all_folders
        if not winners_tab.folder_filter_combo.get():
            winners_tab.folder_filter_combo.set("All")

    def filter_library_by_folder(self):
        """Filters the library treeview based on the dropdown selection."""
        winners_tab = self.get_winners_tab()
        if not winners_tab or not winners_tab.folder_filter_combo:
            return

        selected_folder = winners_tab.folder_filter_combo.get()

        self.clear_tab_results(self.winners_tab_id)

        if selected_folder == "All":
            winners = self.winners_manager.winners
        else:
            winners = self.winners_manager.get_winners_by_folder(selected_folder)

        for winner in winners:
            self.add_winner_to_tab(winner.to_dict())
