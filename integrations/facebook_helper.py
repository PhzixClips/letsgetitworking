"""
Helper functions for parsing and manipulating Facebook URLs.
"""

import re
from typing import Optional

def extract_fb_id(url: str) -> Optional[str]:
    """
    Extracts a numeric video ID from various Facebook URL formats.
    Looks for 10-20 digit numbers in common URL patterns.
    """
    # Patterns for various FB video URLs
    patterns = [
        r"(?:/reel/|/videos/|/watch/\?v=|[?&]v=)(\d{10,20})",
        r"fb\.watch/v/(\d{10,20})", # Less common, but possible
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None

def canonicalize_facebook_url(url: str, mobile: bool = False) -> Optional[str]:
    """
    Converts a Facebook video URL to a canonical 'watch' format.

    Args:
        url: The original Facebook URL.
        mobile: If True, returns the 'm.facebook.com' version.

    Returns:
        A canonical URL string or None if no ID could be extracted.
    """
    video_id = extract_fb_id(url)
    if not video_id:
        return None

    if mobile:
        return f"https://m.facebook.com/watch/?v={video_id}"
    else:
        return f"https://www.facebook.com/watch/?v={video_id}"
