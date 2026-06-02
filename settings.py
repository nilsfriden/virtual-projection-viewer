"""
settings.py — Persistent settings via JSON file.
v1.4

Saves and loads user preferences between sessions.
File is stored next to the executable / script.
"""

import json
from pathlib import Path

# Settings file location: same directory as the script
SETTINGS_FILE = Path(__file__).parent / "settings.json"

# Defaults
DEFAULTS = {
    # Camera
    "camera_target_x": 0.0,
    "camera_target_y": 0.0,
    "camera_target_z": 0.0,
    "camera_azimuth": 0.0,
    "camera_elevation": 15.0,
    "camera_distance": 10.0,
    "camera_fov": 60.0,

    # Model transform
    "model_pos_x": 0.0,
    "model_pos_y": 0.0,
    "model_pos_z": 0.0,
    "model_scale": 1.0,
    "model_rot_y": 0.0,
    "brightness": 1.0,

    # Texture
    "texture_rotation": 3,
    "res_scale": 2,

    # Paths / sources
    "last_model_path": "",
    "last_ndi_source": "",
}


def load_settings() -> dict:
    """Load settings from JSON file, falling back to defaults."""
    settings = dict(DEFAULTS)
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            # Merge saved values over defaults (handles new keys gracefully)
            for key in DEFAULTS:
                if key in saved:
                    settings[key] = saved[key]
            print(f"[settings] Loaded from {SETTINGS_FILE}")
        else:
            print("[settings] No settings file found, using defaults")
    except Exception as e:
        print(f"[settings] Error loading settings: {e}")
    return settings


def save_settings(settings: dict):
    """Save settings to JSON file."""
    try:
        # Only save keys that exist in DEFAULTS (don't store junk)
        clean = {k: settings[k] for k in DEFAULTS if k in settings}
        with open(SETTINGS_FILE, "w") as f:
            json.dump(clean, f, indent=2)
        print(f"[settings] Saved to {SETTINGS_FILE}")
    except Exception as e:
        print(f"[settings] Error saving settings: {e}")
