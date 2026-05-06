"""
config_loader.py
----------------
Loads config.json from the project root (MP3Wrapped/).
All scripts import from here instead of hardcoding paths.

Setup: copy config.example.json → config.json and fill in your paths.
"""

import json
import os
import sys
from pathlib import Path

# The project root is the parent of the scripts/ folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    config_path = PROJECT_ROOT / "config.json"

    if not config_path.exists():
        print(
            f"\n config.json not found at {config_path}\n"
            f"    Copy {example_path} → config.json and fill in your paths.\n"
        )
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


_cfg = load_config()

# -- Project-internal paths (never need configuring) --------------------------
LOG_PATH       = str(PROJECT_ROOT / "master.log")
STATE_FILE     = str(PROJECT_ROOT / "state.json")
RAW_DIR        = str(PROJECT_ROOT / "raw")
PROCESSED_DIR  = str(PROJECT_ROOT / "processed")

# -- output paths (set in config.json) ------------------------------------
_out_ = Path(_cfg["output_dir"])

OUTPUT_DIR     = str(_out_)
OUTPUT_HTML        = str(Path(_cfg.get("wrapped_html", str(_out_ / "wrapped.html"))))
OUTPUT_JSON        = str(_out_ / "mp3_monthly_albums.json")
COVERS_JSON        = str(_out_ / "mp3_albums.json")
COVER_FOLDER       = str(_out_ / "covers")

# -- Music source folder -------------------------------------------------------
MUSIC_FOLDER = _cfg.get("music_folder", "")

# -- API Keys (set in config.json) --------------------------------------------
SPOTIFY_CLIENT_SECRET = _cfg.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_CLIENT_ID = _cfg.get("SPOTIFY_CLIENT_ID")
MUSIC_BRAINZ_USER_AGENT = _cfg.get("MUSIC_BRAINZ_USER_AGENT")
