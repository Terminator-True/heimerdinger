"""Riot match (v5) parsing utilities.

This module provides functions to normalize a Riot v5 match JSON into
aggregated player metrics suitable for downstream analysis.
"""
from typing import Any, Dict, List, Optional


def _safe_get_info(match_json: Dict[str, Any]) -> Dict[str, Any]:
    return match_json.get("info", {}) or {}


def _get_game_start_millis(match_json: Dict[str, Any]) -> int:
    info = _safe_get_info(match_json)
    # Riot match formats vary; prefer gameStartTimestamp, then gameCreation
    return int(info.get("gameStartTimestamp") or info.get("gameCreation") or 0)


def _get_game_duration_seconds(match_json: Dict[str, Any]) -> float:
    info = _safe_get_info(match_json)
    # gameDuration may be in seconds (typical) or milliseconds in some dumps
    dur = info.get("gameDuration")
    if dur is None:
        return 0.0
    # If duration is suspiciously large (> 100000), assume milliseconds
    try:
        dur_f = float(dur)
    except (TypeError, ValueError):
        return 0.0
    if dur_f > 100000:  # milliseconds
        return dur_f / 1000.0
    return dur_f


def compute_cs(participant: Dict[str, Any]) -> int:
    """Compute creep score (CS) as minions + neutral minions.

    Riot sometimes reports totalMinionsKilled and neutralMinionsKilled separately.
    """
    tm = participant.get("totalMinionsKilled", 0) or 0
    nm = participant.get("neutralMinionsKilled", 0) or 0
    try:
        return int(tm) + int(nm)
    except (TypeError, ValueError):
        return 0


def compute_cs_per_min(cs: int, game_duration_seconds: float) -> float:
    """Compute CS per minute. Returns 0.0 if duration is zero.

    Args:
        cs: creep score
        game_duration_seconds: game duration in seconds
    """
    if not game_duration_seconds or game_duration_seconds <= 0:
        return 0.0
    return cs / (game_duration_seconds / 60.0)


def compute_kda(kills: int, deaths: int, assists: int) -> float:
    """Compute a KDA-like metric: (kills + assists) / max(1, deaths).

    This avoids division by zero and matches typical esports analytics.
    """
    try:
        k = int(kills) if kills is not None else 0
        d = int(deaths) if deaths is not None else 0
        a = int(assists) if assists is not None else 0
    except (TypeError, ValueError):
        return 0.0
    return (k + a) / max(1, d)


def parse_match(match_json: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a Riot v5 match JSON into normalized player metrics.

    Returns a dict with keys:
      - gameStartMillis: int
      - gameDurationSeconds: float
      - players: list of player metric dicts

    Each player metric dict contains at least:
      puuid, summonerName, championName, role, kills, deaths, assists,
      cs, cs_per_min, goldEarned, visionScore, damageDealtToChampions,
      teamId, win (bool), timestamp

    The parser is defensive and accepts minimal match payloads used in tests.
    """
    info = _safe_get_info(match_json)
    participants = info.get("participants") or []
    game_start = _get_game_start_millis(match_json)
    game_dur = _get_game_duration_seconds(match_json)

    players: List[Dict[str, Any]] = []
    for p in participants:
        puuid = p.get("puuid") or p.get("player", {}).get("puuid")
        summoner_name = p.get("summonerName") or p.get("player", {}).get("summonerName")
        champion = p.get("championName") or p.get("champion")
        role = p.get("teamPosition") or p.get("role") or p.get("lane")

        kills = p.get("kills", 0)
        deaths = p.get("deaths", 0)
        assists = p.get("assists", 0)

        cs = compute_cs(p)
        cs_per_min = compute_cs_per_min(cs, game_dur)
        kda = compute_kda(kills, deaths, assists)

        player_metrics: Dict[str, Any] = {
            "puuid": puuid,
            "summonerName": summoner_name,
            "championName": champion,
            "role": role,
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "cs": cs,
            "cs_per_min": cs_per_min,
            "kda": kda,
            "goldEarned": p.get("goldEarned", 0),
            "visionScore": p.get("visionScore", 0),
            "damageDealtToChampions": p.get("totalDamageDealtToChampions", p.get("damageDealtToChampions", 0)),
            "teamId": p.get("teamId"),
            "win": bool(p.get("win", False)),
            "timestamp": game_start,
        }
        players.append(player_metrics)

    return {
        "gameStartMillis": game_start,
        "gameDurationSeconds": game_dur,
        "players": players,
    }


class MatchParser:
    """Compatibility wrapper exposing a MatchParser with parse_match staticmethod.

    Some codepaths expect a MatchParser class. Provide a thin wrapper that
    delegates to the module-level parse_match function.
    """

    @staticmethod
    def parse_match(match_json: Dict[str, Any]) -> Dict[str, Any]:
        return parse_match(match_json)
