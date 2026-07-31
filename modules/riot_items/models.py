"""Data Dragon item data models (dataclasses, no dependencies).

Mirrors the item.json entry shape: Item, ItemGold, ItemImage, ItemData.
Because dataclasses have no alias support, the ``from`` JSON key is mapped
via explicit ``item_to_dict``/``item_from_dict`` helpers.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ItemGold:
    total: int = 0
    base: int = 0
    sell: int = 0
    purchasable: bool = False


@dataclass
class ItemImage:
    full: str = ""
    sprite: str = ""
    group: str = "item"
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0


@dataclass
class Item:
    name: str
    description: str = ""
    plaintext: Optional[str] = None
    gold: ItemGold = field(default_factory=ItemGold)
    from_: List[str] = field(default_factory=list)
    into: List[str] = field(default_factory=list)
    stats: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    image: Optional[ItemImage] = None

    @property
    def is_craftable(self) -> bool:
        """True when the item is built from components."""
        return len(self.from_) > 0

    @property
    def component_count(self) -> int:
        """Number of component items needed to build this item."""
        return len(self.from_)

    def get_image_url(self, version: str) -> str:
        """CDN URL for the item icon, or "" when the item has no image."""
        if not self.image or not self.image.full:
            return ""
        return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{self.image.full}"


@dataclass
class ItemData:
    type: str = "item"
    version: str = ""
    data: Dict[str, Item] = field(default_factory=dict)


def item_to_dict(item: Item) -> Dict[str, Any]:
    """Serialize an Item to a plain dict, using the JSON ``from`` key."""
    d: Dict[str, Any] = {
        "name": item.name,
        "description": item.description,
        "plaintext": item.plaintext,
        "gold": {
            "total": item.gold.total,
            "base": item.gold.base,
            "sell": item.gold.sell,
            "purchasable": item.gold.purchasable,
        },
        "from": list(item.from_),
        "into": list(item.into),
        "stats": dict(item.stats),
        "tags": list(item.tags),
    }
    if item.image is not None:
        d["image"] = {
            "full": item.image.full,
            "sprite": item.image.sprite,
            "group": item.image.group,
            "x": item.image.x,
            "y": item.image.y,
            "w": item.image.w,
            "h": item.image.h,
        }
    return d


def item_from_dict(d: Dict[str, Any]) -> Item:
    """Parse an item.json entry tolerantly.

    Missing or malformed sub-objects fall back to defaults instead of
    raising, so a partially broken cache entry still decodes.
    """
    name = d.get("name", "")
    if not isinstance(name, str):
        name = ""

    gold_d = d.get("gold")
    gold = ItemGold(
        total=gold_d.get("total", 0) if isinstance(gold_d, dict) else 0,
        base=gold_d.get("base", 0) if isinstance(gold_d, dict) else 0,
        sell=gold_d.get("sell", 0) if isinstance(gold_d, dict) else 0,
        purchasable=gold_d.get("purchasable", False) if isinstance(gold_d, dict) else False,
    )

    image_d = d.get("image")
    image = None
    if isinstance(image_d, dict):
        image = ItemImage(
            full=image_d.get("full", "") if isinstance(image_d.get("full"), str) else "",
            sprite=image_d.get("sprite", "") if isinstance(image_d.get("sprite"), str) else "",
            group=image_d.get("group", "item") if isinstance(image_d.get("group"), str) else "item",
            x=image_d.get("x", 0) if isinstance(image_d.get("x"), int) else 0,
            y=image_d.get("y", 0) if isinstance(image_d.get("y"), int) else 0,
            w=image_d.get("w", 0) if isinstance(image_d.get("w"), int) else 0,
            h=image_d.get("h", 0) if isinstance(image_d.get("h"), int) else 0,
        )

    from_raw = d.get("from")
    into_raw = d.get("into")
    stats_raw = d.get("stats")
    tags_raw = d.get("tags")

    return Item(
        name=name,
        description=d.get("description", "") or "",
        plaintext=d.get("plaintext"),
        gold=gold,
        from_=list(from_raw) if isinstance(from_raw, list) else [],
        into=list(into_raw) if isinstance(into_raw, list) else [],
        stats=dict(stats_raw) if isinstance(stats_raw, dict) else {},
        tags=list(tags_raw) if isinstance(tags_raw, list) else [],
        image=image,
    )
