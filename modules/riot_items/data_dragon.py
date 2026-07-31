"""Data Dragon static-data client (keyless CDN, httpx, no new dependencies).

The constructor is network-free: a pinned ``version`` is used as-is, and
otherwise version resolution happens lazily on the first fetch that needs
it. This lets offline callers construct the client without I/O.

Error contract: httpx.HTTPError (including timeouts and transport errors)
and ValueError (malformed JSON) from versions.json / item.json propagate to
the caller, which decides how to degrade.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from .item_cache import ItemCache
from .models import Item, item_from_dict


def _parse_xy(version: str) -> Optional[Tuple[int, int]]:
    """Parse the major.minor part of a version string, or None when invalid."""
    parts = version.split(".")
    if len(parts) < 2:
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


class DataDragonClient:
    BASE_URL = "https://ddragon.leagueoflegends.com/cdn"
    VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"

    def __init__(
        self,
        locale: str = "es_ES",
        version: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        client: Optional[httpx.Client] = None,
    ):
        self.locale = locale
        self.version = version  # None -> resolved lazily on first fetch
        self.cache_dir = cache_dir
        # Network-free: the client is created but never used at construction.
        self._client = client or httpx.Client(timeout=10.0)
        self._items_cache: Optional[Dict[str, Item]] = None
        self._items_version: Optional[str] = None
        self._versions_cache: Optional[List[str]] = None

    # ------------------------------------------------------------------
    # versions
    # ------------------------------------------------------------------

    def _get_versions(self) -> List[str]:
        """versions.json, memoized for the client lifetime."""
        if self._versions_cache is None:
            resp = self._client.get(self.VERSIONS_URL)
            resp.raise_for_status()
            self._versions_cache = list(resp.json())
        return self._versions_cache

    def get_latest_version(self) -> str:
        """Return the newest released version (versions[0])."""
        return self._get_versions()[0]

    def resolve_version(self, game_version: str) -> str:
        """Pin a match patch (``info.gameVersion``) to a released DDragon version.

        Returns the released version with major.minor <= the match's, choosing
        the highest such version; falls back to the latest version when none
        qualifies or the match version is unparseable.
        """
        versions = self._get_versions()
        target = _parse_xy(game_version)
        if target is None:
            return versions[0]

        best: Optional[str] = None
        best_xy: Optional[Tuple[int, int]] = None
        for v in versions:
            xy = _parse_xy(v)
            if xy is None or xy > target:
                continue
            if best_xy is None or xy > best_xy:
                best = v
                best_xy = xy
        return best if best is not None else versions[0]

    # ------------------------------------------------------------------
    # items
    # ------------------------------------------------------------------

    def _effective_version(self, version: Optional[str]) -> str:
        """Resolve the version to use for a fetch (lazy latest when unset)."""
        if version is not None:
            return version
        if self.version is None:
            self.version = self.get_latest_version()
        return self.version

    def fetch_items(self, version: Optional[str] = None) -> Dict[str, Item]:
        """Return all items keyed by string id.

        Order: in-memory cache (version-guarded) -> per-version disk cache ->
        one httpx GET, then persisted to the disk cache.
        """
        effective = self._effective_version(version)
        if self._items_cache is not None and self._items_version == effective:
            return self._items_cache

        disk = ItemCache(effective, self.locale, cache_dir=self.cache_dir)
        items = disk.load()
        if items is None:
            url = f"{self.BASE_URL}/{effective}/data/{self.locale}/item.json"
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            raw_items = data.get("data") or {}
            items = {str(item_id): item_from_dict(entry) for item_id, entry in raw_items.items()}
            disk.save(items)

        self._items_cache = items
        self._items_version = effective
        return items

    def get_item_by_id(self, item_id: int, version: Optional[str] = None) -> Optional[Item]:
        """Return the item, or None for id 0 / unknown ids."""
        if item_id in (0, None):
            return None
        return self.fetch_items(version).get(str(item_id))

    def get_items_by_ids(
        self, ids: List[int], version: Optional[str] = None
    ) -> Dict[int, Optional[Item]]:
        """Resolve several ids in one fetch; id 0 / unknown map to None."""
        items = self.fetch_items(version)
        return {item_id: None if item_id in (0, None) else items.get(str(item_id)) for item_id in ids}

    def refresh_cache(self) -> Dict[str, Item]:
        """Clear in-memory and disk caches, then refetch from the network."""
        self._items_cache = None
        self._items_version = None
        version = self._effective_version(None)
        ItemCache(version, self.locale, cache_dir=self.cache_dir).clear()
        return self.fetch_items(version)

    def get_item_image_url(self, item_id: int, version: Optional[str] = None) -> str:
        """CDN icon URL for an item, or "" for id 0 / unknown items."""
        item = self.get_item_by_id(item_id, version)
        if item is None:
            return ""
        return item.get_image_url(self._effective_version(version))
