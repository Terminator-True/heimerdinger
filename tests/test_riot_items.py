"""Unit tests for the modules.riot_items package (Data Dragon static data)."""
import json

import httpx
import pytest
import respx

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
