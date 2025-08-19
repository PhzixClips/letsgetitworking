"""
Preset management for search configurations
"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from config import PRESETS_FILE
from utils.logging import log_upgrade

@dataclass
class SearchPreset:
    """Data class for search preset configuration"""
    name: str
    query: str
    uploaded: str
    count: str
    min_vph: str
    max_duration: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'SearchPreset':
        """Create from dictionary"""
        return cls(
            name=data.get('name', ''),
            query=data.get('query', ''),
            uploaded=data.get('uploaded', 'Any'),
            count=data.get('count', '50'),
            min_vph=data.get('min_vph', '0'),
            max_duration=data.get('max_duration', '')
        )

class PresetManager:
    """Manages search presets for the application"""

    def __init__(self, presets_file: str = PRESETS_FILE):
        self.presets_file = presets_file

    def load_presets(self) -> List[SearchPreset]:
        """Load presets from file"""
        if not os.path.exists(self.presets_file):
            return []

        try:
            with open(self.presets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [SearchPreset.from_dict(preset_data) for preset_data in data]
        except Exception as e:
            log_upgrade(f"Error loading presets: {e}")
            return []

    def save_presets(self, presets: List[SearchPreset]) -> bool:
        """Save presets to file"""
        try:
            data = [preset.to_dict() for preset in presets]
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            log_upgrade(f"Error saving presets: {e}")
            return False

    def add_preset(self, name: str, query: str, uploaded: str,
                   count: str, min_vph: str, max_duration: str = "") -> bool:
        """Add a new preset"""
        if not name.strip():
            return False

        presets = self.load_presets()

        # Check if preset name already exists
        if any(preset.name == name for preset in presets):
            return False

        new_preset = SearchPreset(
            name=name,
            query=query,
            uploaded=uploaded,
            count=count,
            min_vph=min_vph,
            max_duration=max_duration
        )

        presets.append(new_preset)
        return self.save_presets(presets)

    def delete_preset(self, name: str) -> bool:
        """Delete a preset by name"""
        presets = self.load_presets()
        original_count = len(presets)

        presets = [preset for preset in presets if preset.name != name]

        if len(presets) == original_count:
            return False  # Preset not found

        return self.save_presets(presets)

    def get_preset(self, name: str) -> Optional[SearchPreset]:
        """Get a specific preset by name"""
        presets = self.load_presets()
        for preset in presets:
            if preset.name == name:
                return preset
        return None

    def get_preset_names(self) -> List[str]:
        """Get list of all preset names"""
        presets = self.load_presets()
        return [preset.name for preset in presets]

    def update_preset(self, old_name: str, updated_preset: SearchPreset) -> bool:
        """Update an existing preset"""
        presets = self.load_presets()

        for i, preset in enumerate(presets):
            if preset.name == old_name:
                presets[i] = updated_preset
                return self.save_presets(presets)

        return False  # Preset not found
