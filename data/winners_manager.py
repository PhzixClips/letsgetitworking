"""
Winner videos management system
"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from utils.logging import log_upgrade

from dataclasses import dataclass, asdict, field

@dataclass
class WinnerVideo:
    """Data class for winner video"""
    video_id: str
    title: str
    channel_title: str
    viral_score: float
    views: int
    likes: int
    ratio: float
    vph: float
    duration: str
    age: str
    repost_flag: bool
    repost_reason: str
    date_saved: str
    folder: str = "Default"
    notes: str = ""
    display_title: str = ""
    tags: List[str] = field(default_factory=list)
    has_transcript: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'WinnerVideo':
        """Create from dictionary"""
        # Fallback for old data: if display_title is missing, use original title
        display_title = data.get('display_title', data.get('title', ''))
        if not display_title:
             display_title = data.get('title', '')

        return cls(
            video_id=data.get('video_id', ''),
            title=data.get('title', ''),
            channel_title=data.get('channel_title', ''),
            viral_score=data.get('viral_score', 0.0),
            views=data.get('views', 0),
            likes=data.get('likes', 0),
            ratio=data.get('ratio', 0.0),
            vph=data.get('vph', 0.0),
            duration=data.get('duration', '00:00'),
            age=data.get('age', ''),
            repost_flag=data.get('repost_flag', False),
            repost_reason=data.get('repost_reason', ''),
            date_saved=data.get('date_saved', ''),
            folder=data.get('folder', 'Default'),
            notes=data.get('notes', ''),
            display_title=display_title,
            tags=data.get('tags', []),
            has_transcript=data.get('has_transcript', False)
        )

class WinnersManager:
    """Manages winner videos and folders"""

    def __init__(self, winners_file: str = 'winners.json'):
        self.winners_file = winners_file
        self.winners: List[WinnerVideo] = []
        self.folders: List[str] = ["Default"]
        self.load_winners()

    def load_winners(self) -> bool:
        """Load winners from file"""
        if not os.path.exists(self.winners_file):
            return True

        try:
            with open(self.winners_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Load winners
            winners_data = data.get('winners', [])
            self.winners = [WinnerVideo.from_dict(w) for w in winners_data]

            # Load folders
            self.folders = data.get('folders', ["Default"])
            if "Default" not in self.folders:
                self.folders.insert(0, "Default")

            log_upgrade(f"Loaded {len(self.winners)} winners in {len(self.folders)} folders")
            return True

        except Exception as e:
            log_upgrade(f"Error loading winners: {e}")
            return False

    def save_winners(self) -> bool:
        """Save winners to file"""
        try:
            data = {
                'winners': [winner.to_dict() for winner in self.winners],
                'folders': self.folders,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.winners_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            log_upgrade(f"Saved {len(self.winners)} winners")
            return True

        except Exception as e:
            log_upgrade(f"Error saving winners: {e}")
            return False

    def add_winner(self, video_data: Dict, folder: str, notes: str = "") -> bool:
        """Add a video to winners"""
        video_id = video_data.get('video_id', '')

        if self.get_winner_by_id(video_id):
            return False

        from .transcripts_manager import TranscriptsManager
        tm = TranscriptsManager()
        has_transcript = tm.exists(video_id)

        winner = WinnerVideo(
            video_id=video_id,
            title=video_data.get('title', ''),
            channel_title=video_data.get('channel_title', ''),
            display_title=video_data.get('display_title', video_data.get('title', '')),
            viral_score=video_data.get('viral_score', 0.0),
            views=video_data.get('views', 0),
            likes=video_data.get('likes', 0),
            ratio=video_data.get('ratio', 0.0),
            vph=video_data.get('vph', 0.0),
            duration=video_data.get('duration', '00:00'),
            age=video_data.get('age', ''),
            repost_flag=video_data.get('repost_flag', False),
            repost_reason=video_data.get('repost_reason', ''),
            date_saved=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            folder=folder,
            notes=notes,
            tags=video_data.get('tags', []),
            has_transcript=has_transcript
        )

        self.winners.append(winner)
        return self.save_winners()

    def remove_winner(self, video_id: str) -> bool:
        """Remove a winner by video ID"""
        original_count = len(self.winners)
        self.winners = [w for w in self.winners if w.video_id != video_id]

        if len(self.winners) < original_count:
            return self.save_winners()
        return False

    def get_winner_by_id(self, video_id: str) -> Optional[WinnerVideo]:
        """Get winner by video ID"""
        for winner in self.winners:
            if winner.video_id == video_id:
                return winner
        return None

    def get_winners_by_folder(self, folder: str) -> List[WinnerVideo]:
        """Get all winners in a specific folder"""
        return [w for w in self.winners if w.folder == folder]

    def move_winner_to_folder(self, video_id: str, new_folder: str) -> bool:
        """Move winner to different folder"""
        if new_folder not in self.folders:
            return False

        winner = self.get_winner_by_id(video_id)
        if winner:
            winner.folder = new_folder
            return self.save_winners()
        return False

    def add_folder(self, folder_name: str) -> bool:
        """Add a new folder"""
        if folder_name and folder_name not in self.folders:
            self.folders.append(folder_name)
            return self.save_winners()
        return False

    def remove_folder(self, folder_name: str) -> bool:
        """Remove a folder (moves videos to Default)"""
        if folder_name == "Default" or folder_name not in self.folders:
            return False

        # Move all videos in this folder to Default
        for winner in self.winners:
            if winner.folder == folder_name:
                winner.folder = "Default"

        self.folders.remove(folder_name)
        return self.save_winners()

    def rename_folder(self, old_name: str, new_name: str) -> bool:
        """Rename a folder"""
        if old_name not in self.folders or new_name in self.folders or not new_name:
            return False

        # Update folder name in winners
        for winner in self.winners:
            if winner.folder == old_name:
                winner.folder = new_name

        # Update folder list
        folder_index = self.folders.index(old_name)
        self.folders[folder_index] = new_name

        return self.save_winners()

    def get_all_folders(self) -> List[str]:
        """Get all folder names"""
        return self.folders.copy()

    def get_winner_count(self) -> int:
        """Get total number of winners"""
        return len(self.winners)

    def get_folder_count(self, folder: str) -> int:
        """Get number of winners in folder"""
        return len(self.get_winners_by_folder(folder))

    def update_winner_notes(self, video_id: str, notes: str) -> bool:
        """Update notes for a winner"""
        winner = self.get_winner_by_id(video_id)
        if winner:
            winner.notes = notes
            return self.save_winners()
        return False

    def update_winner(self, video_id: str, new_data: Dict) -> bool:
        """Update an existing winner with new data."""
        winner = self.get_winner_by_id(video_id)
        if not winner:
            return False

        winner.display_title = new_data.get('display_title', winner.display_title)
        winner.notes = new_data.get('notes', winner.notes)
        winner.tags = new_data.get('tags', winner.tags)
        winner.has_transcript = new_data.get('has_transcript', winner.has_transcript)

        if 'folder' in new_data and new_data['folder'] in self.folders:
            winner.folder = new_data['folder']

        # For forward compatibility, update any other fields that might be in new_data
        for key, value in new_data.items():
            if hasattr(winner, key) and key not in ['video_id', 'title', 'date_saved']:
                setattr(winner, key, value)

        return self.save_winners()

    def search_winners(self, query: str) -> List[WinnerVideo]:
        """Search winners by title"""
        query_lower = query.lower()
        return [
            w for w in self.winners
            if query_lower in w.title.lower() or query_lower in w.notes.lower()
        ]