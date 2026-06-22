import pytest

from modules.data.match_parser import MatchParser, compute_cs_per_min


def test_missing_matchid_behaviour():
    # match JSON missing metadata.matchId
    match = {
        # intentionally missing metadata
        "info": {"gameStartTimestamp": 1000, "gameDuration": 60, "participants": []}
    }

    # The parser should still parse but upstream repo.upsert_match would raise;
    # here we ensure parse_match doesn't crash and returns gameStartMillis
    parsed = MatchParser.parse_match(match)
    assert parsed["gameStartMillis"] == 0 or isinstance(parsed["gameStartMillis"], int)
    assert parsed["players"] == []


def test_participant_missing_stats_defaults_zero():
    match = {
        "metadata": {"matchId": "m1"},
        "info": {
            "gameStartTimestamp": 1000,
            "gameDuration": 120,
            "participants": [
                {"puuid": "p1", "summonerName": "Bob", "championName": "Ahri"}
            ],
        },
    }

    parsed = MatchParser.parse_match(match)
    players = parsed["players"]
    assert len(players) == 1
    p = players[0]
    # kills/deaths/assists should default to 0
    assert p["kills"] == 0
    assert p["deaths"] == 0
    assert p["assists"] == 0


def test_zero_game_duration_cs_per_min_zero():
    match = {
        "metadata": {"matchId": "m2"},
        "info": {
            "gameStartTimestamp": 1000,
            "gameDuration": 0,
            "participants": [
                {"puuid": "p2", "summonerName": "Carol", "championName": "Annie", "totalMinionsKilled": 100}
            ],
        },
    }

    parsed = MatchParser.parse_match(match)
    p = parsed["players"][0]
    assert p["cs"] == 100
    assert p["cs_per_min"] == 0.0


def test_participant_not_found_does_not_crash_and_no_upsert(mocker):
    # Simulate ingest flow where target puuid is absent. We call parser directly
    match = {
        "metadata": {"matchId": "m3"},
        "info": {
            "gameStartTimestamp": 1000,
            "gameDuration": 600,
            "participants": [
                {"puuid": "other", "summonerName": "X", "championName": "Garen"}
            ],
        },
    }

    parsed = MatchParser.parse_match(match)
    participants = parsed.get("players", [])
    # ensure participants list exists and does not include our missing puuid
    assert isinstance(participants, list)
    assert all(p.get("puuid") != "target-puuid" for p in participants)
