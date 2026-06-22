"""Configuration management utilities.

Provides helpers to list available team files and load a team by name or path.
"""
from pathlib import Path
from typing import List, Dict, Any
import json


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def list_teams() -> List[str]:
    """List JSON files available in the config/ directory.

    Returns list of filenames (not full paths).
    """
    if not CONFIG_DIR.exists():
        return []
    return [p.name for p in CONFIG_DIR.glob("*.json") if p.is_file()]


def get_team(team_name_or_path: str) -> Dict[str, Any]:
    """Load a team configuration.

    If team_name_or_path points to an existing file path, load it directly.
    Otherwise treat it as a filename under the project's config/ directory.
    """
    candidate = Path(team_name_or_path)
    if candidate.exists():
        with open(candidate, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # try under config dir
    under = CONFIG_DIR / team_name_or_path
    if under.exists():
        with open(under, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # try appending .json
    under_json = CONFIG_DIR / (team_name_or_path + ".json")
    if under_json.exists():
        with open(under_json, "r", encoding="utf-8") as fh:
            return json.load(fh)

    raise FileNotFoundError(f"Team file not found: {team_name_or_path}")
