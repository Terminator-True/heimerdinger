"""Per-version disk cache for Data Dragon item data.

Stores the parsed item dicts at ``{cache_dir}/{version}_{locale}.json`` so
each (version, locale) pair is fetched from the network at most once.
"""
import json
from pathlib import Path
from typing import Dict, Optional

from .models import Item, item_from_dict, item_to_dict


class ItemCache:
    def __init__(self, version: str, locale: str, cache_dir: Optional[Path] = None):
        self.version = version
        self.locale = locale
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path("cache") / "riot_items"
        self.cache_file = self.cache_dir / f"{version}_{locale}.json"

    def load(self) -> Optional[Dict[str, Item]]:
        """Return the cached items, or None when missing or corrupt.

        Corruption covers invalid JSON, non-dict payloads, and entries that
        are not dicts — all treated as a cache miss so the caller refetches.
        """
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return None
            return {
                str(item_id): item_from_dict(item_data)
                for item_id, item_data in data.items()
            }
        except (ValueError, KeyError, TypeError, OSError, AttributeError):
            return None

    def save(self, items: Dict[str, Item]) -> None:
        """Persist items as plain dicts keyed by string item id."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        data = {str(item_id): item_to_dict(item) for item_id, item in items.items()}
        with open(self.cache_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def exists(self) -> bool:
        return self.cache_file.exists()

    def clear(self) -> None:
        if self.cache_file.exists():
            self.cache_file.unlink()
