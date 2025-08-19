"""
Facebook video extraction using yt-dlp.
"""
import subprocess
from pathlib import Path
from typing import Optional

from config import YT_DLP_PATH
from utils.logging import log_upgrade


def is_facebook_url(url: str) -> bool:
    """Check if the URL is a Facebook URL."""
    return "facebook.com" in url.lower() or "fb.watch" in url.lower()

def normalize_facebook_url(url: str) -> str:
    """
    Basic normalization for a Facebook URL.
    - Trims whitespace.
    - More complex normalization (like removing tracking params) can be added later.
    """
    return url.strip()

def download_facebook_video(url: str, cookies_path: Optional[str], output_path: Path) -> bool:
    """
    Download a video from Facebook using yt-dlp.
    """
    try:
        output_template = str(output_path / '%(title)s.%(ext)s')
        command = [
            YT_DLP_PATH,
            '-f', 'bestvideo*+bestaudio/best',
            '--merge-output-format', 'mp4',
            '--no-mtime',
            '-o', output_template,
            url
        ]

        if cookies_path:
            command.extend(['--cookies', cookies_path])

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )

        stdout, stderr = process.communicate()

        if process.returncode == 0:
            log_upgrade(f"Successfully downloaded Facebook video: {url}")
            return True
        else:
            log_upgrade(f"Facebook download failed for {url}: {stderr}")
            return False

    except Exception as e:
        log_upgrade(f"Facebook download error for {url}: {e}")
        return False
