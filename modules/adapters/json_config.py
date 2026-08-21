"""Config-source adapter delegating to the existing ``config_manager``."""

from typing import Any

from modules import config_manager


class JsonConfigSource:
    """ConfigSourcePort implementation backed by the JSON files under ``config/``."""

    def get_team(self, name_or_path: str) -> dict[str, Any]:
        return config_manager.get_team(name_or_path)

    def get_embeddings_config(self) -> dict[str, Any]:
        return config_manager.get_embeddings_config()

    def get_ddragon_config(self) -> dict[str, Any]:
        return config_manager.get_ddragon_config()
