import json
import os
from typing import Dict, List, Optional, Tuple

_DEFAULT_PROMPTS = {
    "modes": [
        {
            "id": "research_insight",
            "name": "Research & Insight (with score)",
            "prompt": (
                "The following is the complete transcript of a YouTube video. "
                "I am using it for research purposes to extract key insights, strategies, and actionable advice.\n\n"
                "Your tasks:\n"
                "1) Act as a domain expert on this topic — analyze the content, identify the most important points, and synthesize them into a structured, detailed response that can be applied in real-world scenarios.\n"
                "2) Rate the overall quality and completeness of the transcript's context on a scale from 1 to 100.\n"
                "3) List the flaws or weaknesses that lower the score (e.g., missing details, unclear reasoning, bias, outdated information).\n"
                "4) Provide a clear, actionable plan for improving the content to reach a perfect 100.\n\n"
                "Transcript:"
            )
        }
    ],
    "default_mode_id": "research_insight"
}

def load_prompts(json_path: str = None) -> Tuple[List[Dict], str]:
    """
    Load prompt modes from JSON.
    Returns (modes, default_mode_id).
    Falls back to in-code defaults if file missing or invalid.
    """
    if json_path is None:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prompts.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        modes = data.get("modes", [])
        default_id = data.get("default_mode_id") or (modes[0]["id"] if modes else "research_insight")
        if not modes:
            raise ValueError("No modes found")
        return modes, default_id
    except Exception:
        return _DEFAULT_PROMPTS["modes"], _DEFAULT_PROMPTS["default_mode_id"]

def find_prompt_by_id(modes: List[Dict], mode_id: str) -> Optional[Dict]:
    for m in modes:
        if m.get("id") == mode_id:
            return m
    return None
