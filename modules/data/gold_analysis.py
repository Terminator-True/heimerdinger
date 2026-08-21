"""Gold-focused analysis over raw match data.

``player_matches.parsed_metrics`` only carries ``goldEarned``; gold spent,
items and the challenges block (GPM) live in the raw ``matches`` collection,
so these helpers join by matchId to build per-match gold rows.

Item metadata (name, gold value, stat bonuses) is resolved through the Data
Dragon client in ``modules/riot_items`` — one lazily-created shared client
with a per-version disk cache. Resolution failures degrade gracefully: rows
keep the item ids and report empty names/stats instead of failing.
"""
from typing import Any, Dict, List, Optional

from modules.data.report_builder import ReportBuilder, get_full_match
from modules.logger import get_logger

logger = get_logger(__name__)

# Slots 0..5 are the build; slot 6 is the (free) trinket.
BUILD_SLOTS = ("item0", "item1", "item2", "item3", "item4", "item5")

_item_client = None


def _get_item_client():
    global _item_client
    if _item_client is None:
        from modules.riot_items.data_dragon import DataDragonClient

        _item_client = DataDragonClient()
    return _item_client


def _item_ids_of(participant: Dict[str, Any]) -> List[int]:
    ids = []
    for slot in BUILD_SLOTS:
        iid = participant.get(slot)
        if iid:  # 0 = empty slot
            try:
                ids.append(int(iid))
            except (TypeError, ValueError):
                pass
    return ids


def _merge_item_stats(items: List[Any]) -> Dict[str, float]:
    """Sum each stat bonus (AD/AP/AS/HP/...) across the build."""
    merged: Dict[str, float] = {}
    for item in items:
        if item is None:
            continue
        for key, value in (item.stats or {}).items():
            try:
                merged[key] = round(merged.get(key, 0.0) + float(value), 2)
            except (TypeError, ValueError):
                pass
    return merged


def _resolve_items(item_ids: List[int], game_version: Optional[str]) -> Dict[str, Any]:
    """Resolve item ids -> names / gold value / merged stats.

    Fallback: return raw ids with empty names/stats when the ddragon fetch
    fails (offline, network error), mirroring prompt_builder's degradation.
    """
    if not item_ids:
        return {"ids": [], "names": [], "gold_value": 0, "stats": {}}
    try:
        client = _get_item_client()
        version = client.resolve_version(game_version) if game_version else None
        resolved = client.get_items_by_ids(item_ids, version=version)
    except Exception as exc:
        logger.warning("Item resolution failed for %s: %s", item_ids, exc)
        return {"ids": item_ids, "names": [], "gold_value": 0, "stats": {}}

    names: List[str] = []
    gold_value = 0
    items: List[Any] = []
    for item_id in item_ids:
        item = resolved.get(item_id)
        if item is None:
            continue
        names.append(item.name)
        gold_value += item.gold.total
        items.append(item)
    return {
        "ids": item_ids,
        "names": names,
        "gold_value": round(gold_value, 2),
        "stats": _merge_item_stats(items),
    }


def _gold_row(participant: Dict[str, Any], match: Dict[str, Any], match_id: str) -> Dict[str, Any]:
    """One gold row for a participant of a raw match doc."""
    info = match.get("info") or {}
    challenges = participant.get("challenges") or {}
    earned = participant.get("goldEarned") or 0
    spent = participant.get("goldSpent") or 0
    return {
        "matchId": match_id,
        "puuid": participant.get("puuid"),
        "summonerName": participant.get("summonerName"),
        "timestamp": (
            participant.get("timestamp")
            or info.get("gameStartTimestamp")
            or info.get("gameCreation")
        ),
        "win": bool(participant.get("win")),
        "champion": participant.get("championName"),
        "role": participant.get("teamPosition") or participant.get("individualPosition"),
        "teamId": participant.get("teamId"),
        "goldEarned": earned,
        "goldSpent": spent,
        "gold_diff": earned - spent,
        "gpm": challenges.get("goldPerMinute"),
        "itemsPurchased": participant.get("itemsPurchased"),
        "consumablesPurchased": participant.get("consumablesPurchased"),
        "items": _resolve_items(_item_ids_of(participant), info.get("gameVersion")),
    }


def gold_rows_for_match(match: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gold rows for all participants of one raw match doc."""
    info = match.get("info") or {}
    match_id = (match.get("metadata") or {}).get("matchId") or info.get("gameId")
    return [_gold_row(p, match, match_id) for p in (info.get("participants") or [])]


def gold_row_for_player(db, match_id: str, puuid: str) -> Optional[Dict[str, Any]]:
    """Gold row for one player in one match (join via the raw match doc)."""
    match = get_full_match(db, match_id)
    if not match:
        return None
    for participant in (match.get("info") or {}).get("participants") or []:
        if participant.get("puuid") == puuid:
            return _gold_row(participant, match, match_id)
    return None


def get_player_gold_rows(db, puuid: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Recent gold rows for a player, most recent first (via player_matches)."""
    col = db.get_collection("player_matches")
    docs = list(col.find({"player_puuid": puuid}).sort("_id", -1).limit(limit))
    rows = []
    for doc in docs:
        match_id = doc.get("matchId") or doc.get("id")
        if not match_id:
            continue
        row = gold_row_for_player(db, match_id, puuid)
        if row:
            rows.append(row)
    return rows


def aggregate_gold(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mean/median/p25/p75 over the numeric gold metrics + spend ratio."""
    acc: Dict[str, List[float]] = {}
    numeric_keys = ("goldEarned", "goldSpent", "gold_diff", "gpm")
    for row in rows:
        for key in numeric_keys:
            ReportBuilder._accumulate_numeric(acc, key, row.get(key))
        ReportBuilder._accumulate_numeric(acc, "item_gold_value", (row.get("items") or {}).get("gold_value"))

    agg = ReportBuilder._aggregate(acc, numeric_keys + ("item_gold_value",))

    # How much of earned gold is actually spent (consumables + build).
    ratios = []
    for row in rows:
        earned = row.get("goldEarned")
        spent = row.get("goldSpent")
        if earned:
            ratios.append(spent / earned)
    if ratios:
        agg["gold_spend_ratio"] = round(sum(ratios) / len(ratios), 3)

    agg["games_analyzed"] = len(rows)
    agg["wins"] = sum(1 for r in rows if r.get("win"))
    return agg