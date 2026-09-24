"""Tests for modules.data.timeline — compaction and per-minute derivation."""

from modules.data.timeline import (
    build_player_timeline,
    compact_timeline,
    lane_opponent_id,
)


def _pf(pid, gold, cs, jungle, xp, level):
    """A raw participantFrame carrying the fields compaction must drop."""
    return {
        "participantId": pid,
        "totalGold": gold,
        "currentGold": gold // 2,
        "xp": xp,
        "level": level,
        "minionsKilled": cs - jungle,
        "jungleMinionsKilled": jungle,
        "position": {"x": 1, "y": 2},
        "championStats": {"abilityHaste": 10},
        "damageStats": {"totalDamageDoneToChampions": 123},
        "goldPerSecond": 3,
        "timeEnemySpentControlled": 0,
    }


def _raw_timeline(minutes, with_opponent=True):
    frames = []
    for m in range(minutes + 1):
        pfs = {"1": _pf(1, 500 + 400 * m, 5 * m, 0, 100 * m, m // 3 + 1)}
        if with_opponent:
            pfs["2"] = _pf(2, 500 + 300 * m, 4 * m, 1, 90 * m, m // 3 + 1)
        frames.append({
            "timestamp": m * 60000,
            "participantFrames": pfs,
            "events": [{"type": "CHAMPION_KILL", "timestamp": m * 60000}],
        })
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


# ---------------------------------------------------------------- compaction

def test_compact_keeps_numeric_frames_and_drops_bulk():
    compact = compact_timeline(_raw_timeline(2))

    assert compact["matchId"] == "M1"
    assert compact["frameInterval"] == 60000
    assert compact["participants"] == [
        {"participantId": 1, "puuid": "me"},
        {"participantId": 2, "puuid": "opp"},
    ]

    frame = compact["frames"][0]
    assert set(frame) == {"timestamp", "participantFrames"}
    assert "events" not in frame
    assert "events" not in compact

    pf = frame["participantFrames"]["1"]
    assert set(pf) == {
        "participantId", "totalGold", "currentGold", "xp", "level",
        "minionsKilled", "jungleMinionsKilled",
    }
    assert "championStats" not in pf
    assert "damageStats" not in pf
    assert "goldPerSecond" not in pf
    assert "position" not in pf
    assert "timeEnemySpentControlled" not in pf
    assert pf["totalGold"] == 500


def test_compact_participants_falls_back_to_metadata_order():
    raw = _raw_timeline(1)
    # No explicit info.participants: mapping comes from metadata order.
    del raw["info"]["participants"]
    compact = compact_timeline(raw)

    assert compact["participants"] == [
        {"participantId": 1, "puuid": "me"},
        {"participantId": 2, "puuid": "opp"},
    ]


def test_compact_is_defensive_on_partial_input():
    # No info at all, no frames, non-dict input: never raises.
    assert compact_timeline({}) == {
        "matchId": None, "frameInterval": 60000, "participants": [], "frames": [],
    }
    assert compact_timeline(None) == {}
    partial = compact_timeline({
        "metadata": {"matchId": "M2"},
        "info": {"frames": [{"timestamp": 0}]},  # no participantFrames
    })
    assert partial["frames"] == [{"timestamp": 0, "participantFrames": {}}]


# ------------------------------------------------------------ lane opponent

def test_lane_opponent_id_normal_match():
    assert lane_opponent_id(_match_doc(), 1) == 2
    assert lane_opponent_id(_match_doc(), 2) == 1


def test_lane_opponent_id_none_when_role_missing():
    assert lane_opponent_id(_match_doc(position=""), 1) is None
    # Participant absent from the match doc -> None, not a crash.
    assert lane_opponent_id(_match_doc(), 99) is None
    assert lane_opponent_id({}, 1) is None


# ---------------------------------------------------------- build series

def test_build_player_timeline_series_diff_and_milestones():
    compact = compact_timeline(_raw_timeline(22))
    built = build_player_timeline(compact, _match_doc(), "me")

    assert built["matchId"] == "M1"
    assert built["puuid"] == "me"
    assert built["frameIntervalMs"] == 60000

    # minute math: frame timestamp // frameInterval.
    assert [e["minute"] for e in built["series"][:3]] == [0, 1, 2]
    # cs = minionsKilled + jungleMinionsKilled.
    assert built["series"][10]["cs"] == 50
    assert built["series"][10]["gold"] == 500 + 400 * 10
    assert built["series"][10]["xp"] == 1000
    assert built["series"][10]["level"] == 10 // 3 + 1

    assert built["opponent"] == {"puuid": "opp", "championName": "Zed"}
    assert built["opponentSeries"][10]["cs"] == 40  # 39 lane + 1 jungle
    # goldDiff = ours - theirs; we are ahead, so positive.
    assert built["diff"][10]["goldDiff"] == (500 + 4000) - (500 + 3000)
    assert built["diff"][10]["goldDiff"] > 0
    assert built["diff"][10]["csDiff"] == 50 - 40

    ms = built["milestones"]
    assert ms["goldAt10"] == 500 + 400 * 10
    assert ms["csAt10"] == 50
    assert ms["goldAt15"] == 500 + 400 * 15
    assert ms["goldAt20"] == 500 + 400 * 20
    assert ms["goldDiffAt20"] == (500 + 400 * 20) - (500 + 300 * 20)


def test_build_player_timeline_short_game_has_no_at20():
    compact = compact_timeline(_raw_timeline(18))
    built = build_player_timeline(compact, _match_doc(), "me")

    ms = built["milestones"]
    # The game reached 15 but not 20.
    assert ms["goldAt15"] is not None
    assert ms["csAt15"] is not None
    assert ms["goldAt20"] is None
    assert ms["csAt20"] is None
    assert ms["goldDiffAt20"] is None


def test_build_player_timeline_short_game_has_no_at10():
    compact = compact_timeline(_raw_timeline(5))
    built = build_player_timeline(compact, _match_doc(), "me")
    assert built["milestones"]["goldAt10"] is None
    assert built["milestones"]["goldDiffAt10"] is None


def test_build_player_timeline_no_opponent():
    compact = compact_timeline(_raw_timeline(12))
    built = build_player_timeline(compact, _match_doc(position=""), "me")

    assert built["opponent"] is None
    assert built["opponentSeries"] == []
    assert built["diff"] == []
    assert built["milestones"]["goldDiffAt10"] is None
    # Our own series is still built.
    assert built["series"][10]["cs"] == 50


def test_build_player_timeline_unknown_puuid_is_empty_not_raise():
    compact = compact_timeline(_raw_timeline(12))
    built = build_player_timeline(compact, _match_doc(), "not-in-match")

    assert built["series"] == []
    assert built["opponent"] is None
    assert built["diff"] == []
    assert built["milestones"]["goldAt10"] is None

    assert build_player_timeline(None, _match_doc(), "me") == {}
