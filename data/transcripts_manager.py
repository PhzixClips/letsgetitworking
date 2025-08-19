import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from data.settings_manager import settings_manager

class TranscriptsManager:
    """Manages storing, retrieving, and searching video transcripts."""

    def __init__(self):
        """Initializes the manager and ensures the base transcripts path exists."""
        self.base_path = Path(settings_manager.get("transcripts_path", "transcripts"))
        self.base_path.mkdir(parents=True, exist_ok=True)

    def path_for(self, video_id: str, extension: str = ".json") -> Path:
        """
        Gets the full Path object for a given video ID and extension.

        Args:
            video_id: The unique identifier for the video.
            extension: The file extension (e.g., ".json" or ".txt").

        Returns:
            The full path to the transcript file.
        """
        return self.base_path / f"{video_id}{extension}"

    def exists(self, video_id: str) -> bool:
        """
        Checks if a transcript JSON file exists for a given video ID.

        Args:
            video_id: The video identifier.

        Returns:
            True if the JSON file exists, False otherwise.
        """
        return self.path_for(video_id, ".json").exists()

    def save(self, record: Dict) -> Optional[Path]:
        """
        Saves a transcript record to a JSON file and its raw text to a .txt file.

        Args:
            record: A dictionary containing transcript data.

        Returns:
            The path to the saved JSON file, or None on failure.
        """
        video_id = record.get("video_id")
        if not video_id:
            return None

        json_path = self.path_for(video_id, ".json")
        txt_path = self.path_for(video_id, ".txt")

        try:
            # Save JSON metadata
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=4)

            # Save raw transcript text
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(record.get("text", ""))

            return json_path
        except IOError as e:
            print(f"Error saving transcript for {video_id}: {e}")
            # Clean up partial files if something went wrong
            if json_path.exists():
                os.remove(json_path)
            if txt_path.exists():
                os.remove(txt_path)
            return None

    def load(self, video_id: str) -> Optional[Dict]:
        """
        Loads a transcript record from its JSON file.

        Args:
            video_id: The video identifier.

        Returns:
            A dictionary with the transcript data, or None if not found.
        """
        if not self.exists(video_id):
            return None

        json_path = self.path_for(video_id, ".json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading transcript for {video_id}: {e}")
            return None

    def delete(self, video_id: str) -> bool:
        """
        Deletes a transcript's .json and .txt files.

        Args:
            video_id: The video identifier.

        Returns:
            True if deletion was successful or files didn't exist, False on error.
        """
        json_path = self.path_for(video_id, ".json")
        txt_path = self.path_for(video_id, ".txt")
        deleted = True

        try:
            if json_path.exists():
                os.remove(json_path)
            if txt_path.exists():
                os.remove(txt_path)
        except OSError as e:
            print(f"Error deleting transcript for {video_id}: {e}")
            deleted = False

        return deleted

    def search(self, query: str = "", folder: Optional[str] = None) -> List[Dict]:
        """
        Searches through saved transcripts.

        Args:
            query: A search string to match in title, tags, or text.
            folder: An optional folder name to filter by.

        Returns:
            A list of matching transcript records.
        """
        results = []
        query_lower = query.lower()

        for json_file in self.base_path.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    record = json.load(f)

                # Folder filtering
                if folder and record.get("folder") != folder:
                    continue

                # Query filtering
                if query:
                    matches_query = (
                        query_lower in record.get("title", "").lower() or
                        query_lower in record.get("text", "").lower() or
                        any(query_lower in str(tag).lower() for tag in record.get("tags", []))
                    )
                    if not matches_query:
                        continue

                results.append(record)
            except (IOError, json.JSONDecodeError):
                continue

        return results

    def combine_text(self, video_ids: List[str]) -> str:
        """
        Combines the text of multiple transcripts into a single string.

        Args:
            video_ids: A list of video IDs to combine.

        Returns:
            A single string with all transcript texts concatenated and formatted.
        """
        combined = []
        for video_id in video_ids:
            record = self.load(video_id)
            if record:
                title = record.get('title', 'Unknown Title')
                text = record.get('text', '').strip()
                header = f"==== {title} ({video_id}) ===="
                combined.append(f"{header}\n{text}\n\n")

        return "".join(combined)
