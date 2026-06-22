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
