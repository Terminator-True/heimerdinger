"""Unit tests for gold analysis (modules/data/gold_analysis.py)."""
import types
from unittest.mock import patch

import pytest

from modules.data.gold_analysis import (
    _item_ids_of,
    _resolve_items,
    aggregate_gold,
    gold_rows_for_match,
    get_player_gold_rows,
)


class FakeItem:
    def __init__(self, name, gold_total, stats=None):
        self.name = name
        self.gold = types.SimpleNamespace(total=gold_total)
        self.stats = stats or {}


class FakeItemClient:
    def __init__(self, items):
        self.items = items

    def resolve_version(self, game_version):
        return "14.10.1"

    def get_items_by_ids(self, ids, version=None):
        return {iid: self.items.get(iid) for iid in ids}


@pytest.fixture(autouse=True)
def fake_item_client():
    client = FakeItemClient({
        1001: FakeItem("Botas de velocidad", 300, {"FlatMovementSpeedMod": 45}),
        1055: FakeItem("Espada del rey", 3200, {"FlatPhysicalDamageMod": 55, "FlatAttackSpeedMod": 25}),
    })
    with patch("modules.data.gold_analysis._get_item_client", return_value=client):
        yield


class FakeCol:
    def __init__(self, docs):
        self.docs = docs

    def find(self, filt):
        return self

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self.docs[:n]

    def find_one(self, filt):
        puuid = filt.get("player_puuid")
        match_id = filt.get("matchId")
        meta_mid = (filt.get("metadata") or {}).get("matchId")
        for d in self.docs:
            if puuid and d.get("player_puuid") != puuid:
                continue
            if match_id and d.get("matchId") != match_id:
                continue
            if meta_mid and (d.get("metadata") or {}).get("matchId") != meta_mid:
                continue
            return d
        return None


class FakeDB:
    def __init__(self, player_matches=None, matches=None):
        self._cols = {
            "player_matches": FakeCol(player_matches or []),
            "matches": FakeCol(matches or []),
        }

    def get_collection(self, name):
        return self._cols.get(name, FakeCol([]))


def make_participant(puuid, earned, spent, items, gpm=None, win=True):
    p = {
        "puuid": puuid,
        "summonerName": f"p-{puuid}",
        "teamId": 100,
        "teamPosition": "MID",
        "championName": "Ahri",
        "goldEarned": earned,
        "goldSpent": spent,
        "itemsPurchased": 10,
        "consumablesPurchased": 3,
        "win": win,
        "timestamp": 1700000000000,
    }
    for i, iid in enumerate(items):
        p[f"item{i}"] = iid
    if gpm is not None:
        p["challenges"] = {"goldPerMinute": gpm}
    return p


def make_match(match_id, participants):
    return {
        "metadata": {"matchId": match_id},
        "info": {
            "gameVersion": "14.10.1",
            "gameStartTimestamp": 1700000000000,
            "participants": participants,
        },
    }


def test_item_ids_skips_empty_slots():
    p = make_participant("p1", 1000, 900, [1001, 0, 1055])
    assert _item_ids_of(p) == [1001, 1055]


def test_resolve_items_merges_names_gold_and_stats():
    resolved = _resolve_items([1001, 1055], "14.10.1")
    assert resolved["names"] == ["Botas de velocidad", "Espada del rey"]
    assert resolved["gold_value"] == 3500
    assert resolved["stats"]["FlatPhysicalDamageMod"] == 55
    assert resolved["stats"]["FlatMovementSpeedMod"] == 45


def test_resolve_items_falls_back_on_network_error():
    with patch("modules.data.gold_analysis._get_item_client", side_effect=RuntimeError("offline")):
        resolved = _resolve_items([1001], "14.10.1")
    assert resolved["names"] == []
    assert resolved["gold_value"] == 0


def test_gold_rows_for_match_builds_rows():
    match = make_match("m1", [make_participant("p1", 12000, 11500, [1001, 1055], gpm=420)])
    rows = gold_rows_for_match(match)
    assert len(rows) == 1
    row = rows[0]
    assert row["goldEarned"] == 12000
    assert row["goldSpent"] == 11500
    assert row["gold_diff"] == 500
    assert row["gpm"] == 420
    assert row["items"]["gold_value"] == 3500


def test_get_player_gold_rows_joins_by_match_id():
    pm = [{"player_puuid": "p1", "matchId": "m1", "role": "MID"}]
    matches = [make_match("m1", [make_participant("p1", 12000, 11500, [1001])])]
    rows = get_player_gold_rows(FakeDB(player_matches=pm, matches=matches), "p1", limit=5)
    assert len(rows) == 1
    assert rows[0]["matchId"] == "m1"


def test_get_player_gold_rows_skips_missing_raw_match():
    pm = [{"player_puuid": "p1", "matchId": "ghost"}]
    rows = get_player_gold_rows(FakeDB(player_matches=pm, matches=[]), "p1", limit=5)
    assert rows == []


def test_aggregate_gold_computes_stats_and_ratio():
    rows = [
        {"goldEarned": 10000, "goldSpent": 8000, "gold_diff": 2000, "gpm": 400,
         "items": {"gold_value": 7500}, "win": True},
        {"goldEarned": 12000, "goldSpent": 11500, "gold_diff": 500, "gpm": 450,
         "items": {"gold_value": 10000}, "win": False},
    ]
    agg = aggregate_gold(rows)
    assert agg["games_analyzed"] == 2
    assert agg["wins"] == 1
    assert agg["goldEarned"] == 11000  # mean
    assert agg["gold_diff"] == 1250  # mean
    assert round(agg["gold_spend_ratio"], 2) == round((8000 / 10000 + 11500 / 12000) / 2, 2)
    assert agg["item_gold_value"] == 8750  # mean
