"""Configuration management utilities.

Provides helpers to list available team files and load a team by name or path.
"""
from pathlib import Path
from typing import List, Dict, Any
import json


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


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


_EMBEDDINGS_DEFAULTS: Dict[str, Any] = {
    "persist_directory": "chromadb_store",
    "collection_name": "heimerdinger",
    "embedding_model": "all-MiniLM-L6-v2",
    "distance_threshold": 1.0,
}


def get_embeddings_config() -> Dict[str, Any]:
    """Return embeddings/vector-store config.

    Reads config/embeddings.json if present, else falls back to hardcoded
    defaults. Raises a clear error if a config value is present but invalid
    (empty embedding_model).
    """
    config = dict(_EMBEDDINGS_DEFAULTS)
    path = CONFIG_DIR / "embeddings.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            config.update(json.load(fh))

    if not config.get("embedding_model"):
        raise ValueError(
            "Invalid embeddings config: 'embedding_model' is missing or empty"
        )

    return config
