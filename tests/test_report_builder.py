import json
from pathlib import Path

from modules.data.report_builder import (
    ReportBuilder,
    extract_team_composition,
    render_match_snapshot,
)


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


def test_build_player_report_enriched_from_parsed_metrics(tmp_path):
    """build_player_report should extract metrics from parsed_metrics only (no N+1)."""
    db = FakeDB()
    pm = db.get_collection("player_matches")

    champion_name = "Yasuo"
    puuid = "player-yasuo"
    match_id = "m_rich_01"

    # player_matches entry with rich data in parsed_metrics
    pm[match_id] = {
        "player_puuid": puuid,
        "matchId": match_id,
        "championName": champion_name,
        "role": "MIDDLE",
        "parsed_metrics": {
            "cs_per_min": 7.0,
            "kda": 4.33,
            "goldEarned": 14500,
            "totalDamageDealtToChampions": 28500,
            "visionScore": 25,
            "wardsPlaced": 12,
            "dragonKills": 2,
            "baronKills": 1,
            "ch_goldPerMinute": 483.0,
            "ch_killParticipation": 0.65,
        },
    }

    rb = ReportBuilder(output_dir=str(tmp_path / "reports_enriched"))
    report = rb.build_player_report(puuid, db)

    assert report["player"] == puuid
    assert report["games_analyzed"] == 1
    assert report["champion"] == champion_name

    metrics = report["metrics"]
    # fields from parsed_metrics
    assert abs(metrics["cs_per_min"] - 7.0) < 1e-6
    assert abs(metrics["kda"] - 4.33) < 1e-6
    assert metrics.get("goldEarned") == 14500
    assert metrics.get("totalDamageDealtToChampions") == 28500
    assert metrics.get("visionScore") == 25
    assert metrics.get("wardsPlaced") == 12
    assert metrics.get("dragonKills") == 2
    assert metrics.get("baronKills") == 1
    assert metrics.get("ch_goldPerMinute") == 483.0
    assert metrics.get("ch_killParticipation") == 0.65

    # aggregations (mean = same as value since only 1 game)
    assert metrics.get("goldEarned_median") == 14500


def test_build_match_report_from_parsed(tmp_path):
    """build_match_report extracts metrics from parsed_metrics (no full match lookup)."""
    db = FakeDB()

    puuid = "p-match-report"
    match_id = "m_bmr_01"

    match_doc = {
        "player_puuid": puuid,
        "matchId": match_id,
        "champion": "LeBlanc",
        "role": "MIDDLE",
        "parsed_metrics": {
            "cs_per_min": 7.5,
            "kda": 9.0,
            "goldEarned": 15500,
            "totalDamageDealtToChampions": 32000,
            "ch_goldPerMinute": 581.0,
        },
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


def test_build_player_report_empty(tmp_path):
    """Zero-match report returns status='empty' with player info."""
    db = FakeDB()
    rb = ReportBuilder(output_dir=str(tmp_path / "empty"))
    report = rb.build_player_report("missing-puuid", db)

    assert report["status"] == "empty"
    assert report["player"] == "missing-puuid"
    assert "detail" in report


def test_build_player_report_error_on_exception(tmp_path):
    """Exception in build_player_report returns status='error'."""
    class BrokenDB(dict):
        def get_collection(self, name):
            raise RuntimeError("get_collection failed")

    db = BrokenDB()

    rb = ReportBuilder(output_dir=str(tmp_path / "error"))
    report = rb.build_player_report("broken-player", db)

    assert report["status"] == "error"
    assert report["player"] == "broken-player"
    assert "detail" in report


def test_build_match_report_error(tmp_path):
    """Exception in build_match_report returns status='error'."""
    match_doc = {}  # missing all fields → will cause KeyError/AttributeError

    rb = ReportBuilder(output_dir=str(tmp_path))
    report = rb.build_match_report(match_doc, None)

    assert report["status"] == "error"
    assert "detail" in report


def test_render_match_snapshot_two_teams():
    """One compact Spanish line per participant, grouped by team."""
    doc = {
        "metadata": {"matchId": "m1"},
        "info": {
            "participants": [
                {"summonerName": "Alice", "teamId": 100, "individualPosition": "top",
                 "championName": "Garen", "kills": 3, "deaths": 2, "assists": 5,
                 "challenges": {"laneMinionsFirst10Minutes": 42, "goldPerMinute": 410,
                                "damagePerMinute": 520},
                 "visionScore": 21, "win": True},
                {"summonerName": "Bob", "teamId": 200, "individualPosition": "jungle",
                 "championName": "Lee Sin", "kills": 1, "deaths": 4, "assists": 2,
                 "challenges": {"laneMinionsFirst10Minutes": 30, "goldPerMinute": 380,
                                "damagePerMinute": 300},
                 "visionScore": 15, "win": False},
            ],
            "teams": [{"teamId": 100}, {"teamId": 200}],
        },
    }

    out = render_match_snapshot(doc)

    assert out.index("Equipo 1:") < out.index("Equipo 2:")
    assert "Jugador: Alice | Rol: TOP | Campeón: Garen | KDA: 3/2/5" in out
    assert "CS@10: 42 | GPM: 410 | DPM: 520 | Visión: 21 | Victoria: Sí" in out
    assert "Jugador: Bob | Rol: JUNGLE | Campeón: Lee Sin | KDA: 1/4/2" in out
    assert "Victoria: No" in out


def test_render_match_snapshot_empty():
    """Empty participants produce an empty string."""
    assert render_match_snapshot({"info": {"participants": []}}) == ""
    assert render_match_snapshot({}) == ""


def test_render_match_snapshot_keeps_participants_without_team_id():
    """Participants missing teamId, or with a teamId absent from info.teams,
    must still be rendered (one line each), not silently dropped."""
    doc = {
        "metadata": {"matchId": "m3"},
        "info": {
            "participants": [
                {"summonerName": "Alice", "teamId": 100, "individualPosition": "top",
                 "championName": "Garen", "kills": 3, "deaths": 2, "assists": 5,
                 "challenges": {"laneMinionsFirst10Minutes": 42, "goldPerMinute": 410,
                                "damagePerMinute": 520},
                 "visionScore": 21, "win": True},
                {"summonerName": "Bob", "individualPosition": "jungle",
                 "championName": "Lee Sin", "kills": 1, "deaths": 4, "assists": 2,
                 "challenges": {"laneMinionsFirst10Minutes": 30, "goldPerMinute": 380,
                                "damagePerMinute": 300},
                 "visionScore": 15, "win": False},
                {"summonerName": "Carol", "teamId": 300, "individualPosition": "mid",
                 "championName": "Ahri", "kills": 5, "deaths": 3, "assists": 7,
                 "challenges": {"laneMinionsFirst10Minutes": 38, "goldPerMinute": 400,
                                "damagePerMinute": 480},
                 "visionScore": 18, "win": True},
            ],
            "teams": [{"teamId": 100}, {"teamId": 200}],
        },
    }

    out = render_match_snapshot(doc)

    assert "Jugador: Alice | Rol: TOP" in out
    assert "Jugador: Bob | Rol: JUNGLE" in out  # no teamId → not dropped
    assert "Jugador: Carol | Rol: MID" in out   # teamId 300 not in info.teams → not dropped
    assert out.count("Jugador:") == 3  # every participant appears exactly once


def test_extract_team_composition_returns_per_team_champions():
    doc = {
        "info": {
            "participants": [
                {"championName": "Yone", "teamId": 100},
                {"championName": "Lee Sin", "teamId": 100},
                {"championName": "Ahri", "teamId": 100},
                {"championName": "Garen", "teamId": 200},
                {"championName": "Lux", "teamId": 200},
            ]
        }
    }
    comp = extract_team_composition(doc)
    assert comp[100] == ["Yone", "Lee Sin", "Ahri"]
    assert comp[200] == ["Garen", "Lux"]


def test_extract_team_composition_skips_missing_fields():
    doc = {
        "info": {
            "participants": [
                {"championName": "Yone", "teamId": 100},
                {"championName": "SinEquipo"},           # no teamId -> skipped
                {"teamId": 200},                          # no championName -> skipped
                {"championName": None, "teamId": 100},    # null name -> skipped
            ]
        }
    }
    comp = extract_team_composition(doc)
    assert comp == {100: ["Yone"]}


def test_extract_team_composition_empty_doc():
    assert extract_team_composition({}) == {}
    assert extract_team_composition(None) == {}
    assert extract_team_composition({"info": {"participants": []}}) == {}
