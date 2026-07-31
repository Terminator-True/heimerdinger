"""Unit tests for the modules.riot_items package (Data Dragon static data)."""
import json

import httpx
import pytest
import respx

from modules.riot_items.data_dragon import DataDragonClient
from modules.riot_items.item_cache import ItemCache
from modules.riot_items.models import (
    Item,
    ItemData,
    ItemGold,
    ItemImage,
    item_from_dict,
    item_to_dict,
)

# ---------------------------------------------------------------------------
# shared fixtures
# ---------------------------------------------------------------------------

ITEM_3866 = {
    "name": "Guantes de Bruja",
    "description": "<mainText>Botas de hechicero.</mainText>",
    "plaintext": "Botas de hechicero",
    "gold": {"total": 1100, "base": 700, "sell": 770, "purchasable": True},
    "from": ["1001", "1052"],
    "into": ["3020", "3089"],
    "stats": {"FlatMagicDamageMod": 18, "PercentMovementSpeedMod": 0.045},
    "tags": ["Boots", "MagicDamage"],
    "image": {
        "full": "3866.png",
        "sprite": "item0.png",
        "group": "item",
        "x": 0,
        "y": 0,
        "w": 48,
        "h": 48,
    },
}


def item_json_body(version: str, *entries) -> dict:
    """Build an item.json payload from (id, entry_dict) tuples."""
    data = {str(item_id): entry for item_id, entry in entries}
    return {"type": "item", "version": version, "data": data}


# ---------------------------------------------------------------------------
# models (task 1.1)
# ---------------------------------------------------------------------------


class TestModels:
    def test_item_from_dict_parses_entry(self):
        item = item_from_dict(ITEM_3866)
        assert item.name == "Guantes de Bruja"
        assert item.plaintext == "Botas de hechicero"
        assert item.gold.total == 1100
        assert item.gold.base == 700
        assert item.gold.purchasable is True
        assert item.from_ == ["1001", "1052"]
        assert item.into == ["3020", "3089"]
        assert item.stats["FlatMagicDamageMod"] == 18
        assert item.tags == ["Boots", "MagicDamage"]
        assert item.image.full == "3866.png"

    def test_item_from_dict_tolerates_missing_fields(self):
        item = item_from_dict({"name": "Objeto Mínimo"})
        assert item.name == "Objeto Mínimo"
        assert item.description == ""
        assert item.plaintext is None
        assert item.gold.total == 0
        assert item.gold.purchasable is False
        assert item.from_ == []
        assert item.into == []
        assert item.stats == {}
        assert item.tags == []
        assert item.image is None

    def test_item_to_dict_uses_from_key(self):
        d = item_to_dict(item_from_dict(ITEM_3866))
        assert d["from"] == ["1001", "1052"]
        assert "from_" not in d
        assert d["into"] == ["3020", "3089"]
        assert d["gold"]["total"] == 1100
        assert d["image"]["full"] == "3866.png"

    def test_item_dict_round_trip(self):
        item = item_from_dict(ITEM_3866)
        assert item_from_dict(item_to_dict(item)) == item

    def test_item_is_craftable_and_component_count(self):
        craftable = item_from_dict(ITEM_3866)
        assert craftable.is_craftable is True
        assert craftable.component_count == 2
        bare = Item(name="Objeto Básico")
        assert bare.is_craftable is False
        assert bare.component_count == 0

    def test_item_get_image_url(self):
        item = item_from_dict(ITEM_3866)
        assert (
            item.get_image_url("14.20.1")
            == "https://ddragon.leagueoflegends.com/cdn/14.20.1/img/item/3866.png"
        )
        assert Item(name="Sin imagen").get_image_url("14.20.1") == ""

    def test_itemdata_holds_items(self):
        data = ItemData(version="14.20.1", data={"3866": item_from_dict(ITEM_3866)})
        assert data.type == "item"
        assert data.version == "14.20.1"
        assert data.data["3866"].name == "Guantes de Bruja"

    def test_itemgold_defaults(self):
        gold = ItemGold()
        assert gold.total == 0
        assert gold.base == 0
        assert gold.sell == 0
        assert gold.purchasable is False

    def test_itemimage_defaults(self):
        img = ItemImage()
        assert img.full == ""
        assert img.group == "item"
        assert img.x == 0
        assert img.w == 0


# ---------------------------------------------------------------------------
# item cache (task 1.2)
# ---------------------------------------------------------------------------


class TestItemCache:
    def test_round_trip(self, tmp_path):
        cache = ItemCache("14.20.1", "es_ES", cache_dir=tmp_path)
        items = {"3866": item_from_dict(ITEM_3866), "1001": Item(name="Zapato Rápido")}
        cache.save(items)
        assert cache.load() == items

    def test_save_creates_parent_dirs(self, tmp_path):
        cache_dir = tmp_path / "nested" / "riot_items"
        cache = ItemCache("14.20.1", "es_ES", cache_dir=cache_dir)
        cache.save({"3866": item_from_dict(ITEM_3866)})
        assert cache.exists()

    def test_missing_returns_none(self, tmp_path):
        cache = ItemCache("14.20.1", "es_ES", cache_dir=tmp_path)
        assert cache.load() is None
        assert cache.exists() is False

    def test_corrupt_json_returns_none(self, tmp_path):
        cache = ItemCache("14.20.1", "es_ES", cache_dir=tmp_path)
        cache_file = tmp_path / "14.20.1_es_ES.json"
        cache_file.write_text("{not valid json", encoding="utf-8")
        assert cache.load() is None

    def test_wrong_shape_json_returns_none(self, tmp_path):
        cache = ItemCache("14.20.1", "es_ES", cache_dir=tmp_path)
        cache_file = tmp_path / "14.20.1_es_ES.json"
        cache_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        assert cache.load() is None
        cache_file.write_text(json.dumps({"3866": "not a dict"}), encoding="utf-8")
        assert cache.load() is None

    def test_clear(self, tmp_path):
        cache = ItemCache("14.20.1", "es_ES", cache_dir=tmp_path)
        cache.save({"3866": item_from_dict(ITEM_3866)})
        assert cache.exists()
        cache.clear()
        assert cache.exists() is False
        assert cache.load() is None

    def test_version_locale_filename(self, tmp_path):
        cache = ItemCache("14.20.1", "es_ES", cache_dir=tmp_path)
        cache.save({"3866": item_from_dict(ITEM_3866)})
        assert (tmp_path / "14.20.1_es_ES.json").exists()


# ---------------------------------------------------------------------------
# data dragon client (task 1.3)
# ---------------------------------------------------------------------------

VERSIONS_URL = DataDragonClient.VERSIONS_URL
ITEM_URL = f"{DataDragonClient.BASE_URL}/14.20.1/data/es_ES/item.json"


class TestDataDragonClient:
    def test_constructor_makes_no_network_calls(self):
        with respx.mock as rsps:
            DataDragonClient(locale="es_ES")
            assert rsps.calls == []

    def test_get_latest_version_uses_one_get(self):
        with respx.mock as rsps:
            route = rsps.get(VERSIONS_URL).respond(200, json=["15.4.1", "15.3.1"])
            client = DataDragonClient()
            assert client.get_latest_version() == "15.4.1"
            assert route.call_count == 1

    def test_resolve_version_exact_patch(self):
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, json=["15.4.1", "14.20.1", "14.19.1"])
            client = DataDragonClient()
            assert client.resolve_version("14.20.568.9039") == "14.20.1"

    def test_resolve_version_nearest_lower_patch(self):
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, json=["15.4.1", "15.3.1", "15.2.1"])
            client = DataDragonClient()
            assert client.resolve_version("15.3.999") == "15.3.1"

    def test_resolve_version_fallback_to_latest(self):
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, json=["15.4.1", "15.3.1"])
            client = DataDragonClient()
            assert client.resolve_version("1.0.1") == "15.4.1"

    def test_versions_memoized_in_memory(self):
        with respx.mock as rsps:
            route = rsps.get(VERSIONS_URL).respond(
                200, json=["15.4.1", "15.3.1", "14.20.1"]
            )
            client = DataDragonClient()
            client.resolve_version("14.20.568.9039")
            client.resolve_version("15.3.999")
            assert route.call_count == 1

    def test_get_item_by_id_and_special_ids(self, tmp_path):
        body = item_json_body("14.20.1", (3866, ITEM_3866))
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, json=["14.20.1"])
            rsps.get(ITEM_URL).respond(200, json=body)
            client = DataDragonClient(cache_dir=tmp_path)
            item = client.get_item_by_id(3866)
            assert item is not None
            assert item.name == "Guantes de Bruja"
            assert item.gold.total == 1100
            assert client.get_item_by_id(0) is None
            assert client.get_item_by_id(9999) is None

    def test_get_items_by_ids(self, tmp_path):
        body = item_json_body(
            "14.20.1",
            (3866, ITEM_3866),
            (2524, {"name": "Filo del Infinito", "gold": {"total": 3400}}),
        )
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, json=["14.20.1"])
            rsps.get(ITEM_URL).respond(200, json=body)
            client = DataDragonClient(cache_dir=tmp_path)
            result = client.get_items_by_ids([3866, 2524, 9999, 0])
            assert result[3866].name == "Guantes de Bruja"
            assert result[2524].gold.total == 3400
            assert result[9999] is None
            assert result[0] is None

    def test_in_memory_cache_no_refetch(self, tmp_path):
        body = item_json_body("14.20.1", (3866, ITEM_3866))
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, json=["14.20.1"])
            item_route = rsps.get(ITEM_URL).respond(200, json=body)
            client = DataDragonClient(cache_dir=tmp_path)
            client.fetch_items()
            client.fetch_items()
            assert item_route.call_count == 1

    def test_refresh_cache_refetches_from_network(self, tmp_path):
        body = item_json_body("14.20.1", (3866, ITEM_3866))
        with respx.mock as rsps:
            item_route = rsps.get(ITEM_URL).respond(200, json=body)
            client = DataDragonClient(version="14.20.1", cache_dir=tmp_path)
            client.fetch_items()
            assert item_route.call_count == 1
            client.refresh_cache()
            assert item_route.call_count == 2

    def test_multi_version_cache_switch(self, tmp_path):
        body_a = item_json_body("14.20.1", (3866, ITEM_3866))
        body_b = item_json_body(
            "14.21.1", (3866, {**ITEM_3866, "name": "Guantes de Bruja v2"})
        )
        url_b = f"{DataDragonClient.BASE_URL}/14.21.1/data/es_ES/item.json"
        with respx.mock as rsps:
            route_a = rsps.get(ITEM_URL).respond(200, json=body_a)
            route_b = rsps.get(url_b).respond(200, json=body_b)
            client = DataDragonClient(cache_dir=tmp_path)
            client.fetch_items("14.20.1")  # HTTP #1 (no versions.json: explicit version)
            assert route_a.call_count == 1
            client.fetch_items("14.20.1")  # in-memory hit -> 0 HTTP
            assert route_a.call_count == 1
            client.fetch_items("14.21.1")  # HTTP #2
            assert route_b.call_count == 1
            client.fetch_items("14.20.1")  # disk hit -> 0 HTTP
            assert route_a.call_count == 1
            assert len(rsps.calls) == 2

    def test_get_item_image_url(self, tmp_path):
        body = item_json_body("14.20.1", (3866, ITEM_3866))
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, json=["14.20.1"])
            rsps.get(ITEM_URL).respond(200, json=body)
            client = DataDragonClient(cache_dir=tmp_path)
            assert (
                client.get_item_image_url(3866)
                == "https://ddragon.leagueoflegends.com/cdn/14.20.1/img/item/3866.png"
            )
            assert client.get_item_image_url(0) == ""
            assert client.get_item_image_url(9999) == ""

    def test_http_errors_propagate(self, tmp_path):
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(500)
            client = DataDragonClient(cache_dir=tmp_path)
            with pytest.raises(httpx.HTTPError):
                client.get_latest_version()

    def test_malformed_versions_json_propagates(self, tmp_path):
        with respx.mock as rsps:
            rsps.get(VERSIONS_URL).respond(200, text="not json")
            client = DataDragonClient(cache_dir=tmp_path)
            with pytest.raises(ValueError):
                client.get_latest_version()

    def test_item_json_http_error_propagates(self, tmp_path):
        with respx.mock as rsps:
            rsps.get(ITEM_URL).respond(404)
            client = DataDragonClient(version="14.20.1", cache_dir=tmp_path)
            with pytest.raises(httpx.HTTPError):
                client.fetch_items()


# ---------------------------------------------------------------------------
# package exports (task 1.4)
# ---------------------------------------------------------------------------


def test_package_exports():
    from modules import riot_items
    from modules.riot_items import data_dragon, item_cache, models

    assert riot_items.DataDragonClient is data_dragon.DataDragonClient
    assert riot_items.ItemCache is item_cache.ItemCache
    assert riot_items.Item is models.Item
    assert riot_items.ItemGold is models.ItemGold
    assert riot_items.ItemImage is models.ItemImage
    assert riot_items.ItemData is models.ItemData
