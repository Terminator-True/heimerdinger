"""Simple configuration helpers for the project.

Provides small utilities to load JSON config files from the config/ folder.
"""
from pathlib import Path
import json
from typing import Any


CONFIG_DIR = Path(__file__).resolve().parents[0]


def load_json(path: str) -> Any:
    """Load a JSON file relative to the config directory.

    Args:
        path: filename or relative path under config/ (e.g. "team.json").

    Returns:
        Parsed JSON structure.
    """
    p = (CONFIG_DIR / path).resolve()
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_team(team_file: str = "team.json") -> Any:
    """Convenience loader for team files.

    Defaults to config/team.json
    """
    return load_json(team_file)
