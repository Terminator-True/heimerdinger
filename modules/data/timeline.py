"""Timeline compaction and per-minute series derivation (stdlib only).

Riot's match-v5 timeline is dominated by per-frame ``events`` and
``championStats`` / ``damageStats`` blobs that we never read. This module keeps
the useful part:

- ``compact_timeline`` reduces a raw timeline to ``matchId`` +
  ``frameInterval`` + the participantId -> puuid mapping + one dict per frame
  holding only ``timestamp`` and the numeric per-participant counters.
- ``build_player_timeline`` turns a compacted timeline plus the full match doc
  (which carries ``teamPosition`` / ``teamId`` to locate the lane opponent)
  into per-minute series for a player, their lane opponent, the diffs and the
  @10/@15/@20 milestones.

Usage:
    from modules.data.timeline import compact_timeline, build_player_timeline
"""
from typing import Any, Dict, Optional

DEFAULT_FRAME_INTERVAL = 60000
_MILESTONE_MINUTES = (10, 15, 20)

_FRAME_COUNTERS = (
    "totalGold",
    "currentGold",
    "xp",
    "level",
    "minionsKilled",
    "jungleMinionsKilled",
)


def _num(value: Any) -> int:
    """Coerce a possibly-missing Riot counter to a number (default 0)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return 0


def _compact_participants(info: dict, metadata: dict) -> list:
    """participantId -> puuid mapping, preferring the explicit info list.

    Falls back to ``metadata.participants`` order (index i -> participantId
    i + 1) when ``info.participants`` is absent or empty.
    """
    raw = info.get("participants")
    if isinstance(raw, list):
        out = []
        for entry in raw:
            if isinstance(entry, dict):
                out.append({
                    "participantId": entry.get("participantId"),
                    "puuid": entry.get("puuid"),
                })
        if out:
            return out
    meta = metadata.get("participants")
    if isinstance(meta, list):
        return [
            {"participantId": i + 1, "puuid": puuid}
            for i, puuid in enumerate(meta)
        ]
    return []


def _compact_frame(frame: dict) -> dict:
    pfs = frame.get("participantFrames") or {}
    out = {}
    if isinstance(pfs, dict):
        for pid, pf in pfs.items():
            if not isinstance(pf, dict):
                continue
            participant_id = pf.get("participantId")
            if participant_id is None:
                try:
                    participant_id = int(pid)
                except (TypeError, ValueError):
                    participant_id = pid
            entry = {"participantId": participant_id}
            for key in _FRAME_COUNTERS:
                entry[key] = _num(pf.get(key))
            out[str(pid)] = entry
    return {"timestamp": frame.get("timestamp") or 0, "participantFrames": out}


def compact_timeline(timeline_doc: dict) -> dict:
    """Reduce a raw match-v5 timeline to the fields we actually read.

    Drops ``events``, ``championStats``, ``damageStats``, ``goldPerSecond``,
    ``timeEnemySpentControlled`` and ``position``. Never raises on missing or
    partial data.
    """
    if not isinstance(timeline_doc, dict):
        return {}
    metadata = timeline_doc.get("metadata") or {}
    info = timeline_doc.get("info") or {}
    frames = info.get("frames") or []
    return {
        "matchId": metadata.get("matchId") or timeline_doc.get("matchId"),
        "frameInterval": info.get("frameInterval") or DEFAULT_FRAME_INTERVAL,
        "participants": _compact_participants(info, metadata),
        "frames": [
            _compact_frame(frame)
            for frame in frames
            if isinstance(frame, dict)
        ],
    }


def _participant_index(compact: dict) -> Dict[Any, Optional[str]]:
    """Return {participantId: puuid} from a compacted timeline."""
    index = {}
    for entry in (compact or {}).get("participants") or []:
        if isinstance(entry, dict) and entry.get("participantId") is not None:
            index[entry["participantId"]] = entry.get("puuid")
    return index


def _position(participant: dict) -> str:
    return (participant.get("teamPosition") or "").strip()


def lane_opponent_id(match_doc: dict, participant_id: int) -> Optional[int]:
    """Return the opposing participantId in the same lane, or None.

    Uses ``info.participants`` of the full match doc: locate our participant's
    ``teamPosition``, then find the participant with the same position on the
    other ``teamId``. None when our participant is absent, the position is
    missing (e.g. no role) or more than one opponent matches (ambiguous).
    """
    info = (match_doc or {}).get("info") or {}
    participants = info.get("participants") or []
    ours = None
    for p in participants:
        if isinstance(p, dict) and p.get("participantId") == participant_id:
            ours = p
            break
    if ours is None:
        return None

    position = _position(ours)
    if not position:
        return None

    team_id = ours.get("teamId")
    candidates = [
        p.get("participantId")
        for p in participants
        if isinstance(p, dict)
        and _position(p) == position
        and p.get("teamId") != team_id
        and p.get("participantId") is not None
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]


def _frame_participant(frame: dict, participant_id: int) -> Optional[dict]:
    pfs = frame.get("participantFrames") or {}
    if not isinstance(pfs, dict):
        return None
    pf = pfs.get(str(participant_id))
    if pf is None:
        pf = pfs.get(participant_id)
    return pf if isinstance(pf, dict) else None


def _series_for(compact: dict, participant_id: int, interval: int) -> list:
    interval = interval or DEFAULT_FRAME_INTERVAL
    series = []
    for frame in compact.get("frames") or []:
        if not isinstance(frame, dict):
            continue
        pf = _frame_participant(frame, participant_id)
        if pf is None:
            continue
        timestamp = frame.get("timestamp") or 0
        series.append({
            "minute": timestamp // interval,
            "gold": _num(pf.get("totalGold")),
            "cs": _num(pf.get("minionsKilled")) + _num(pf.get("jungleMinionsKilled")),
            "xp": _num(pf.get("xp")),
            "level": _num(pf.get("level")),
        })
    return series


def _champion_name(match_doc: dict, participant_id: int) -> Optional[str]:
    info = (match_doc or {}).get("info") or {}
    for p in info.get("participants") or []:
        if isinstance(p, dict) and p.get("participantId") == participant_id:
            return p.get("championName")
    return None


def _diff(our_series: list, opp_series: list) -> list:
    """Our series minus the opponent's, aligned by minute."""
    opp_by_minute = {e["minute"]: e for e in opp_series}
    diff = []
    for entry in our_series:
        opp = opp_by_minute.get(entry["minute"])
        if opp is None:
            continue
        diff.append({
            "minute": entry["minute"],
            "goldDiff": entry["gold"] - opp["gold"],
            "csDiff": entry["cs"] - opp["cs"],
        })
    return diff


def _milestone_value(series: list, target: int, key: str):
    """Value at the last frame at/before *target*; None if the game ended sooner.

    The game must have reached the target minute, otherwise the milestone is
    None (a 12-minute game has no @20 value). Within that, gaps in the frames
    are tolerated by taking the closest frame at or before the target.
    """
    if not series:
        return None
    if max(e["minute"] for e in series) < target:
        return None
    candidates = [e for e in series if e["minute"] <= target]
    if not candidates:
        return None
    entry = max(candidates, key=lambda e: e["minute"])
    return entry.get(key)


def _empty_milestones() -> dict:
    milestones = {}
    for minute in _MILESTONE_MINUTES:
        milestones[f"goldAt{minute}"] = None
        milestones[f"csAt{minute}"] = None
        milestones[f"goldDiffAt{minute}"] = None
    return milestones


def _milestones(series: list, diff: list) -> dict:
    milestones = _empty_milestones()
    for minute in _MILESTONE_MINUTES:
        milestones[f"goldAt{minute}"] = _milestone_value(series, minute, "gold")
        milestones[f"csAt{minute}"] = _milestone_value(series, minute, "cs")
        milestones[f"goldDiffAt{minute}"] = _milestone_value(diff, minute, "goldDiff")
    return milestones


def build_player_timeline(compact_doc: dict, match_doc: dict, puuid: str) -> dict:
    """Build the per-minute series for *puuid* and their lane opponent.

    Returns an empty series skeleton (never raises) when the participant is
    absent or the input is malformed; ``opponent``/``opponentSeries``/``diff``
    stay empty when no lane opponent can be identified.
    """
    result = {
        "matchId": (compact_doc or {}).get("matchId") if isinstance(compact_doc, dict) else None,
        "puuid": puuid,
        "frameIntervalMs": DEFAULT_FRAME_INTERVAL,
        "series": [],
        "opponent": None,
        "opponentSeries": [],
        "diff": [],
        "milestones": _empty_milestones(),
    }
    if not isinstance(compact_doc, dict):
        return {}

    interval = compact_doc.get("frameInterval") or DEFAULT_FRAME_INTERVAL
    result["frameIntervalMs"] = interval

    index = _participant_index(compact_doc)
    our_pid = next((pid for pid, p in index.items() if p == puuid), None)
    if our_pid is None:
        return result

    result["series"] = _series_for(compact_doc, our_pid, interval)

    opponent_pid = lane_opponent_id(match_doc, our_pid)
    if opponent_pid is not None:
        result["opponent"] = {
            "puuid": index.get(opponent_pid),
            "championName": _champion_name(match_doc, opponent_pid),
        }
        result["opponentSeries"] = _series_for(compact_doc, opponent_pid, interval)
        result["diff"] = _diff(result["series"], result["opponentSeries"])

    result["milestones"] = _milestones(result["series"], result["diff"])
    return result


if __name__ == "__main__":
    def _frame(minute, pid, gold, cs, jungle, xp, level):
        return {
            "timestamp": minute * 60000,
            "participantFrames": {
                str(pid): {
                    "participantId": pid,
                    "totalGold": gold,
                    "currentGold": gold // 2,
                    "xp": xp,
                    "level": level,
                    "minionsKilled": cs - jungle,
                    "jungleMinionsKilled": jungle,
                    # Fields that must be dropped by compaction:
                    "position": {"x": 1, "y": 2},
                    "championStats": {"abilityHaste": 10},
                    "damageStats": {"totalDamageDoneToChampions": 123},
                    "goldPerSecond": 3,
                    "timeEnemySpentControlled": 0,
                },
            },
            "events": [{"type": "CHAMPION_KILL", "timestamp": minute * 60000}],
        }

    def _raw_timeline(minutes, with_opponent=True):
        frames = []
        for m in range(minutes + 1):
            pfs = {str(1): _frame(m, 1, 500 + 400 * m, 5 * m, 0, 100 * m, m // 3 + 1)["participantFrames"]["1"]}
            if with_opponent:
                pfs[str(2)] = _frame(m, 2, 500 + 300 * m, 4 * m, 1, 90 * m, m // 3 + 1)["participantFrames"]["2"]
            frames.append({"timestamp": m * 60000, "participantFrames": pfs,
                           "events": [{"type": "CHAMPION_KILL"}]})
        return {
            "metadata": {"matchId": "M1", "participants": ["me", "opp"]},
            "info": {
                "frameInterval": 60000,
                "participants": [
                    {"participantId": 1, "puuid": "me"},
                    {"participantId": 2, "puuid": "opp"},
                ],
                "frames": frames,
            },
        }

    def _match_doc(position="MIDDLE"):
        return {
            "metadata": {"matchId": "M1"},
            "info": {
                "participants": [
                    {"participantId": 1, "puuid": "me", "teamId": 100,
                     "teamPosition": position, "championName": "Ahri"},
                    {"participantId": 2, "puuid": "opp", "teamId": 200,
                     "teamPosition": "MIDDLE", "championName": "Zed"},
                ],
            },
        }

    raw = _raw_timeline(22)
    compact = compact_timeline(raw)

    # Compaction keeps the numeric counters and the mapping, drops the bulk.
    frame0 = compact["frames"][0]
    assert set(frame0) == {"timestamp", "participantFrames"}
    assert "events" not in frame0 and "events" not in compact
    assert "championStats" not in frame0["participantFrames"]["1"]
    assert "damageStats" not in frame0["participantFrames"]["1"]
    assert "goldPerSecond" not in frame0["participantFrames"]["1"]
    assert "position" not in frame0["participantFrames"]["1"]
    assert set(frame0["participantFrames"]["1"]) == {
        "participantId", "totalGold", "currentGold", "xp", "level",
        "minionsKilled", "jungleMinionsKilled",
    }
    assert _participant_index(compact) == {1: "me", 2: "opp"}

    built = build_player_timeline(compact, _match_doc(), "me")
    series = built["series"]
    assert series[0]["minute"] == 0
    assert series[1]["minute"] == 1
    # cs = minionsKilled + jungleMinionsKilled (our synthetic: all lane cs).
    assert series[10]["cs"] == 50
    assert built["frameIntervalMs"] == 60000

    # Opponent identified and diff has the right sign (we are ahead).
    assert built["opponent"] == {"puuid": "opp", "championName": "Zed"}
    assert built["diff"][10]["goldDiff"] == (500 + 4000) - (500 + 3000)
    assert built["diff"][10]["goldDiff"] > 0
    assert built["diff"][10]["csDiff"] == 50 - 40

    # Milestones: last frame at/before 10/15/20.
    ms = built["milestones"]
    assert ms["goldAt10"] == 500 + 400 * 10
    assert ms["csAt10"] == 50
    assert ms["goldAt20"] == 500 + 400 * 20
    assert ms["goldDiffAt20"] == (500 + 400 * 20) - (500 + 300 * 20)

    # A game shorter than 20 minutes: @20 is None, @15 is the real frame.
    short = build_player_timeline(compact_timeline(_raw_timeline(18)), _match_doc(), "me")
    assert short["milestones"]["goldAt15"] is not None
    assert short["milestones"]["goldAt20"] is None
    assert short["milestones"]["goldDiffAt20"] is None

    # No role -> no lane opponent -> empty opponent data.
    no_role = build_player_timeline(compact, _match_doc(position=""), "me")
    assert no_role["opponent"] is None
    assert no_role["opponentSeries"] == []
    assert no_role["diff"] == []
    assert no_role["milestones"]["goldDiffAt10"] is None
    # Our own series is still derived.
    assert no_role["series"][10]["cs"] == 50

    # Malformed inputs return a skeleton instead of raising.
    assert build_player_timeline(None, _match_doc(), "me") == {}
    missing = build_player_timeline(compact, _match_doc(), "not-in-match")
    assert missing["series"] == [] and missing["opponent"] is None

    print("timeline self-check OK")
