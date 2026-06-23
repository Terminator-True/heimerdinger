import json
from pathlib import Path

from modules.data.report_builder import ReportBuilder


class FakeCol(dict):
    def __init__(self):
        super().__init__()

    def find(self, q):
        # yield all docs that match player_puuid
        for v in list(self.values()):
            if v.get("player_puuid") == q.get("player_puuid"):
                yield v

    def update_one(self, filter_q, update_q, upsert=False):
        key = filter_q.get("player")
        self[key] = update_q["$set"]


class FakeDB(dict):
    def get_collection(self, name):
        return self.setdefault(name, FakeCol())


def test_build_player_report_and_save(tmp_path):
    db = FakeDB()
    pm = db.get_collection("player_matches")

    # create deterministic parsed_metrics entries
    entries = [
        {
            "player_puuid": "player1",
            "matchId": "m1",
            "parsed_metrics": {"cs_per_min": 6.0, "kda": 3.0},
            "championName": "Ahri",
            "role": "Mid",
        },
        {
            "player_puuid": "player1",
            "matchId": "m2",
            "parsed_metrics": {"cs_per_min": 6.4, "kda": 3.2},
            "championName": "Ahri",
            "role": "Mid",
        },
        {
            "player_puuid": "player1",
            "matchId": "m3",
            "parsed_metrics": {"cs_per_min": 6.2, "kda": 3.1},
            "championName": "Zed",
            "role": "Mid",
        },
    ]

    for e in entries:
        pm[e["matchId"]] = e

    rb = ReportBuilder(output_dir=str(tmp_path / "reports"))
    report = rb.build_player_report("player1", db)

    assert report["player"] == "player1"
    assert report["role"] == "Mid"
    assert report["champion"] == "Ahri"  # most common
    assert report["games_analyzed"] == 3
    # averages
    assert abs(report["metrics"]["cs_per_min"] - ((6.0 + 6.4 + 6.2) / 3.0)) < 1e-6
    assert abs(report["metrics"]["kda"] - ((3.0 + 3.2 + 3.1) / 3.0)) < 1e-6

    # saved file exists
    out_file = Path(rb.output_dir) / "player1.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["player"] == "player1"


def test_build_player_report_enriched_from_full_match(tmp_path):
    """build_player_report should enrich metrics when full match docs exist."""
    db = FakeDB()
    pm = db.get_collection("player_matches")
    matches = db.get_collection("matches")

    champion_name = "Yasuo"
    puuid = "player-yasuo"
    match_id = "m_rich_01"

    # full match doc with rich participant data
    full_match = {
        "metadata": {"matchId": match_id, "dataVersion": "2"},
        "info": {
            "gameDuration": 1800,
            "gameMode": "CLASSIC",
            "queueId": 420,
            "gameVersion": "14.10.1",
            "participants": [
                {
                    "puuid": puuid,
                    "championName": champion_name,
                    "individualPosition": "MIDDLE",
                    "teamPosition": "MIDDLE",
                    "win": True,
                    "kills": 8,
                    "deaths": 3,
                    "assists": 5,
                    "totalMinionsKilled": 210,
                    "goldEarned": 14500,
                    "goldSpent": 14000,
                    "totalDamageDealtToChampions": 28500,
                    "damageDealtToObjectives": 5200,
                    "damageDealtToBuildings": 1800,
                    "visionScore": 25,
                    "wardsPlaced": 12,
                    "wardsKilled": 4,
                    "detectorWardsPlaced": 2,
                    "dragonKills": 2,
                    "baronKills": 1,
                    "inhibitorKills": 0,
                    "turretKills": 1,
                    "totalTimeCCDealt": 42.5,
                    "timeCCingOthers": 8.3,
                    "totalTimeSpentDead": 45.0,
                    "longestTimeSpentLiving": 720.0,
                    "item0": 3153,
                    "item1": 3142,
                    "item6": 3340,
                    "teamId": 100,
                    "challenges": {
                        "goldPerMinute": 483.0,
                        "killParticipation": 0.65,
                        "visionScorePerMinute": 0.83,
                        "controlWardsPlaced": 1,
                        "soloKills": 2,
                        "multikills": 1,
                    },
                }
            ],
            "teams": [
                {
                    "teamId": 100,
                    "win": True,
                    "objectives": {
                        "baron": {"kills": 1, "first": True},
                        "dragon": {"kills": 3, "first": True},
                        "tower": {"kills": 8, "first": True},
                        "inhibitor": {"kills": 1, "first": False},
                        "riftHerald": {"kills": 1, "first": True},
                    },
                    "bans": [{"championId": 11}, {"championId": 22}, {"championId": 33},
                             {"championId": 44}, {"championId": 55}],
                }
            ],
        },
    }

    matches[match_id] = full_match

    # player_matches entry (minimal, will be enriched)
    pm[match_id] = {
        "player_puuid": puuid,
        "matchId": match_id,
        "championName": champion_name,
        "role": "MIDDLE",
        "parsed_metrics": {"cs_per_min": 7.0, "kda": 4.33},
    }

    rb = ReportBuilder(output_dir=str(tmp_path / "reports_enriched"))
    report = rb.build_player_report(puuid, db)

    assert report["player"] == puuid
    assert report["games_analyzed"] == 1
    assert report["champion"] == champion_name

    metrics = report["metrics"]
    # legacy fields still present
    assert abs(metrics["cs_per_min"] - 7.0) < 1e-6
    assert abs(metrics["kda"] - 4.33) < 1e-6
    # rich enrichment fields
    assert metrics.get("goldEarned") == 14500
    assert metrics.get("totalDamageDealtToChampions") == 28500
    assert metrics.get("visionScore") == 25
    assert metrics.get("wardsPlaced") == 12
    assert metrics.get("dragonKills") == 2
    assert metrics.get("baronKills") == 1
    assert metrics.get("ch_goldPerMinute") == 483.0
    assert metrics.get("ch_killParticipation") == 0.65
    assert metrics.get("team_baronKills") == 1

    # aggregations (mean = same as value since only 1 game)
    assert metrics.get("goldEarned_median") == 14500


def test_extract_rich_participant_found():
    """_extract_rich_participant returns organised stats for matching puuid."""
    puuid = "p-test-001"
    match_doc = {
        "metadata": {"matchId": "m-001"},
        "info": {
            "gameDuration": 1500,
            "gameMode": "ARAM",
            "queueId": 450,
            "gameVersion": "14.11",
            "participants": [
                {"puuid": "other", "championName": "Lux"},
                {
                    "puuid": puuid,
                    "championName": "Zed",
                    "individualPosition": "MIDDLE",
                    "teamPosition": "MIDDLE",
                    "win": True,
                    "kills": 12,
                    "deaths": 5,
                    "assists": 7,
                    "totalMinionsKilled": 180,
                    "goldEarned": 16000,
                    "goldSpent": 15200,
                    "totalDamageDealtToChampions": 35000,
                    "damageDealtToObjectives": 4100,
                    "damageDealtToBuildings": 900,
                    "visionScore": 18,
                    "wardsPlaced": 8,
                    "wardsKilled": 3,
                    "detectorWardsPlaced": 1,
                    "dragonKills": 0,
                    "baronKills": 0,
                    "turretKills": 2,
                    "totalTimeCCDealt": 30.2,
                    "timeCCingOthers": 6.1,
                    "totalTimeSpentDead": 60.0,
                    "longestTimeSpentLiving": 480.0,
                    "item0": 3142,
                    "item1": 3074,
                    "item6": 3364,
                    "teamId": 200,
                    "challenges": {
                        "goldPerMinute": 640.0,
                        "killParticipation": 0.73,
                        "soloKills": 4,
                    },
                },
            ],
            "teams": [
                {
                    "teamId": 100,
                    "win": False,
                    "objectives": {
                        "baron": {"kills": 0, "first": False},
                        "dragon": {"kills": 1, "first": False},
                        "tower": {"kills": 3, "first": False},
                        "inhibitor": {"kills": 0, "first": False},
                        "riftHerald": {"kills": 0, "first": False},
                    },
                    "bans": [],
                },
                {
                    "teamId": 200,
                    "win": True,
                    "objectives": {
                        "baron": {"kills": 1, "first": True},
                        "dragon": {"kills": 3, "first": True},
                        "tower": {"kills": 9, "first": True},
                        "inhibitor": {"kills": 2, "first": True},
                        "riftHerald": {"kills": 1, "first": True},
                    },
                    "bans": [{"championId": 1}, {"championId": 2}],
                },
            ],
        },
    }

    result = ReportBuilder._extract_rich_participant(match_doc, puuid)

    # identity
    assert result["matchId"] == "m-001"
    assert result["gameDuration"] == 1500
    assert result["gameMode"] == "ARAM"
    assert result["championName"] == "Zed"
    assert result["individualPosition"] == "MIDDLE"
    assert result["win"] is True

    # performance
    assert result["kills"] == 12
    assert result["deaths"] == 5
    assert result["assists"] == 7
    assert result["totalMinionsKilled"] == 180

    # economy
    assert result["goldEarned"] == 16000
    assert result["goldSpent"] == 15200

    # damage
    assert result["totalDamageDealtToChampions"] == 35000
    assert result["damageDealtToObjectives"] == 4100
    assert result["damageDealtToBuildings"] == 900

    # vision
    assert result["visionScore"] == 18
    assert result["wardsPlaced"] == 8

    # objectives
    assert result["turretKills"] == 2
    assert result["dragonKills"] == 0
    assert result["baronKills"] == 0

    # mechanics
    assert result["totalTimeCCDealt"] == 30.2

    # mistakes
    assert result["totalTimeSpentDead"] == 60.0

    # challenges
    assert result["ch_goldPerMinute"] == 640.0
    assert result["ch_killParticipation"] == 0.73
    assert result["ch_soloKills"] == 4

    # items
    assert result["item0"] == 3142
    assert result["item1"] == 3074

    # team
    assert result["team_win"] is True
    assert result["team_baronKills"] == 1
    assert result["team_dragonKills"] == 3
    assert result["team_towerKills"] == 9
    assert result["team_bans"] == [1, 2]


def test_extract_rich_participant_not_found():
    """Returns empty dict when puuid does not appear."""
    match_doc = {
        "metadata": {"matchId": "m-002"},
        "info": {
            "participants": [
                {"puuid": "someone-else", "championName": "Lux"},
            ],
            "teams": [],
        },
    }
    result = ReportBuilder._extract_rich_participant(match_doc, "nobody")
    assert result == {}


def test_extract_rich_participant_none_doc():
    """Returns empty dict when match_doc is None."""
    result = ReportBuilder._extract_rich_participant(None, "p-1")
    assert result == {}


def test_extract_rich_participant_empty_participants():
    """Returns empty dict when participants list is empty."""
    match_doc = {"metadata": {}, "info": {"participants": [], "teams": []}}
    result = ReportBuilder._extract_rich_participant(match_doc, "p-1")
    assert result == {}


def test_build_match_report(tmp_path):
    """build_match_report creates a report and enriches with full match data."""
    db = FakeDB()
    matches = db.get_collection("matches")

    puuid = "p-match-report"
    match_id = "m_bmr_01"

    # full match doc
    full_match = {
        "metadata": {"matchId": match_id},
        "info": {
            "gameDuration": 1600,
            "gameMode": "CLASSIC",
            "queueId": 420,
            "gameVersion": "14.10",
            "participants": [
                {
                    "puuid": puuid,
                    "championName": "LeBlanc",
                    "individualPosition": "MIDDLE",
                    "kills": 10,
                    "deaths": 2,
                    "assists": 8,
                    "goldEarned": 15500,
                    "totalDamageDealtToChampions": 32000,
                    "visionScore": 22,
                    "wardsPlaced": 14,
                    "totalTimeCCDealt": 15.0,
                    "teamId": 100,
                    "challenges": {"goldPerMinute": 581.0},
                }
            ],
            "teams": [
                {"teamId": 100, "win": True, "objectives": {}, "bans": []},
            ],
        },
    }
    matches[match_id] = full_match

    match_doc = {
        "player_puuid": puuid,
        "matchId": match_id,
        "champion": "LeBlanc",
        "role": "MIDDLE",
        "parsed_metrics": {"cs_per_min": 7.5, "kda": 9.0},
    }

    rb = ReportBuilder(output_dir=str(tmp_path))
    report = rb.build_match_report(match_doc, db)

    assert report["player"] == puuid
    assert report["matchId"] == match_id
    assert report["champion"] == "LeBlanc"
    assert report["games_analyzed"] == 1
    assert report["metrics"]["cs_per_min"] == 7.5
    assert report["metrics"]["goldEarned"] == 15500
    assert report["metrics"]["totalDamageDealtToChampions"] == 32000
    assert report["metrics"]["ch_goldPerMinute"] == 581.0
