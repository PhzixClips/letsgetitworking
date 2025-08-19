import os
import glob
import time
from pathlib import Path
from typing import Optional, List

from core.strings import safe_strip

def resolve_final_output_path(stdout: str, outdir: str, vid_id: str) -> Optional[str]:
    """
    Finds the final output file path after a yt-dlp download, with fallbacks.

    Args:
        stdout: The captured stdout from the yt-dlp command.
        outdir: The directory where the file was expected to be saved.
        vid_id: The unique ID of the video being downloaded.

    Returns:
        The absolute path to the output file, or None if it cannot be found.
    """
    # --- Retry loop to handle filesystem delays (e.g., OneDrive, network drives) ---
    for attempt in range(10): # 10 attempts * 0.5s = 5s total
        # --- Strategy 1: Parse stdout for the printed path ---
        lines = stdout.splitlines()
        for line in reversed(lines):
            path_candidate = safe_strip(line)
            if os.path.isabs(path_candidate) and os.path.exists(path_candidate):
                return path_candidate
            # Sometimes the path is relative to the outdir
            if outdir and os.path.exists(os.path.join(outdir, path_candidate)):
                return os.path.join(outdir, path_candidate)

        # --- Strategy 2: Scan for a file matching the video ID ---
        # This is very reliable if our output template is used correctly.
        try:
            # Check for common audio and video extensions
            extensions = ["m4a", "mp3", "wav", "webm", "mp4", "mkv", "mov", "avi"]
            for ext in extensions:
                # Glob for files starting with the video ID
                matches = glob.glob(os.path.join(outdir, f"{vid_id}__*.{ext}"))
                if matches:
                    # Return the most recently modified file among matches
                    latest_file = max(matches, key=os.path.getmtime)
                    return latest_file
        except Exception:
            pass # Ignore errors during globbing

        # --- Strategy 3: Scan for the most recent file in the directory ---
        # This is a last resort and might be inaccurate if other downloads are happening.
        try:
            files = [os.path.join(outdir, f) for f in os.listdir(outdir)]
            if not files:
                time.sleep(0.5)
                continue

            now = time.time()
            recent_files = [f for f in files if os.path.isfile(f) and (now - os.path.getmtime(f)) < 90]

            if recent_files:
                # Prioritize audio extensions
                audio_files = [f for f in recent_files if f.lower().endswith(('.m4a', '.mp3', '.wav'))]
                if audio_files:
                    return max(audio_files, key=os.path.getmtime)

                # Otherwise, return the most recent file of any type
                return max(recent_files, key=os.path.getmtime)
        except Exception:
            pass # Ignore errors during file listing

        # Wait before the next attempt
        time.sleep(0.5)

    return None
