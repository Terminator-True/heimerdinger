import pytest

from modules.data.match_parser import parse_match


def make_minimal_participant(puuid: str = "p1", summonerName: str = "Alice"):
    return {
        "puuid": puuid,
        "summonerName": summonerName,
        "championName": "Ahri",
        "teamId": 100,
        "teamPosition": "MIDDLE",
        "kills": 5,
        "deaths": 2,
        "assists": 3,
        "totalMinionsKilled": 120,
        "neutralMinionsKilled": 10,
        "goldEarned": 10000,
        "visionScore": 20,
        "totalDamageDealtToChampions": 15000,
        "win": True,
    }


def test_parse_match_basic_metrics():
    match = {
        "metadata": {"matchId": "1"},
        "info": {
            "gameStartTimestamp": 1620000000000,
            "gameDuration": 1800,  # seconds
            "participants": [make_minimal_participant(puuid="p1", summonerName="Alice")]
        }
    }

    out = parse_match(match)
    assert out["gameStartMillis"] == 1620000000000
    assert out["gameDurationSeconds"] == 1800
    players = out["players"]
    assert isinstance(players, list) and len(players) == 1
    p = players[0]
    assert p["puuid"] == "p1"
    assert p["summonerName"] == "Alice"
    # CS = 120 + 10
    assert p["cs"] == 130
    # cs_per_min = 130 / (1800/60) = 130 / 30 = 4.333...
    assert abs(p["cs_per_min"] - (130 / 30.0)) < 1e-6
    # kda = (5+3)/max(1,2) = 8/2 = 4.0
    assert abs(p["kda"] - 4.0) < 1e-6
