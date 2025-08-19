from typing import Optional

def safe_strip(value: Optional[str]) -> str:
    """Strips a string if it's not None, otherwise returns an empty string."""
    return value.strip() if isinstance(value, str) else ""
