"""Tests for the FastAPI backend (app.main).

Uses TestClient with the db dependency overridden by an in-memory fake so no
real MongoDB/Riot API is needed. The heavy external flows (coach, embeddings,
ingest with network) are asserted only at the wiring level.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db_dep


class FakeCol:
    def __init__(self, docs):
        self.docs = docs

    def find(self, filt):
        return self

    def __iter__(self):
        return iter(self.docs)

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self.docs[:n]

    def find_one(self, filt):
        puuid = filt.get("player_puuid")
        match_id = filt.get("matchId")
        meta_mid = (filt.get("metadata") or {}).get("matchId")
        has_role = "role" in filt
        for d in self.docs:
            if puuid and d.get("player_puuid") != puuid:
                continue
            if match_id and d.get("matchId") != match_id:
                continue
            if meta_mid and (d.get("metadata") or {}).get("matchId") != meta_mid:
                continue
            if has_role and d.get("role") != filt.get("role"):
                continue
            return d
        return None


class FakeDB:
    def __init__(self, **cols):
        self._cols = cols

    def get_collection(self, name):
        return self._cols.get(name, FakeCol([]))

    def list_collection_names(self):
        return list(self._cols.keys())

    def setdefault(self, key, default=None):
        return self._cols.setdefault(key, default)


def make_fake_db(player_matches=None):
    return FakeDB(
        player_matches=FakeCol(player_matches or []),
        matches=FakeCol([]),
        timelines=FakeCol([]),
        reports=FakeCol([]),
    )


@pytest.fixture(autouse=True)
def override_db():
    fake = make_fake_db()
    app.dependency_overrides[get_db_dep] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "Heimerdinger API"


def test_health_ok(client, override_db):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mongodb": True}


def test_team_returns_config(client):
    with patch("app.main.get_team") as mock_team:
        mock_team.return_value = [{"riotid": "TR Terminator#1998", "role": "Support"}]
        r = client.get("/team")
    assert r.status_code == 200
    assert r.json()[0]["riotid"] == "TR Terminator#1998"


def test_team_not_found(client):
    with patch("app.main.get_team", side_effect=FileNotFoundError("nope")):
        r = client.get("/team", params={"team_path": "missing.json"})
    assert r.status_code == 404


def test_list_player_matches_serializes_object_id(client, override_db):
    from bson import ObjectId

    col = override_db.get_collection("player_matches")
    col.docs = [
        {"_id": ObjectId("000000000000000000000001"), "player_puuid": "p1",
         "matchId": "m1", "championName": "Ahri", "parsed_metrics": {"kills": 5}},
    ]
    r = client.get("/players/p1/matches")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert isinstance(body[0]["_id"], str)
    assert body[0]["matchId"] == "m1"


def test_list_player_matches_empty(client):
    r = client.get("/players/unknown/matches")
    assert r.status_code == 200
    assert r.json() == []


def test_player_report_empty_returns_404(client):
    r = client.get("/players/nobody/report")
    assert r.status_code == 404


def test_player_report_built(client):
    with patch("app.main.ReportBuilder") as mock_rb:
        mock_rb.return_value.build_player_report.return_value = {
            "player": "p1", "games_analyzed": 3, "metrics": {"kda": 2.5},
        }
        r = client.get("/players/p1/report")
    assert r.status_code == 200
    assert r.json()["games_analyzed"] == 3


def test_match_report_not_found(client):
    r = client.get("/players/p1/matches/nope/report")
    assert r.status_code == 404


def test_match_report_found(client, override_db):
    from bson import ObjectId

    col = override_db.get_collection("player_matches")
    col.docs = [
        {"_id": ObjectId("000000000000000000000002"), "player_puuid": "p1",
         "matchId": "m1", "championName": "Ahri", "parsed_metrics": {"kills": 5}},
    ]
    with patch("app.main.ReportBuilder") as mock_rb:
        mock_rb.return_value.build_match_report.return_value = {"player": "p1", "matchId": "m1"}
        r = client.get("/players/p1/matches/m1/report")
    assert r.status_code == 200
    assert r.json()["matchId"] == "m1"


def _raw_timeline(mid="m1", minutes=22):
    """Minimal match-v5 timeline: two laners, one frame per minute."""
    frames = []
    for m in range(minutes + 1):
        frames.append({
            "timestamp": m * 60000,
            "participantFrames": {
                "1": {"participantId": 1, "totalGold": 500 + 400 * m,
                      "currentGold": 200, "xp": 100 * m, "level": 1,
                      "minionsKilled": 5 * m, "jungleMinionsKilled": 0},
                "2": {"participantId": 2, "totalGold": 500 + 300 * m,
                      "currentGold": 200, "xp": 90 * m, "level": 1,
                      "minionsKilled": 4 * m, "jungleMinionsKilled": 0},
            },
        })
    return {
        "metadata": {"matchId": mid, "participants": ["p1", "opp"]},
        "info": {
            "frameInterval": 60000,
            "participants": [
                {"participantId": 1, "puuid": "p1"},
                {"participantId": 2, "puuid": "opp"},
            ],
            "frames": frames,
        },
    }


def _timeline_match(mid="m1", position="MIDDLE"):
    return {
        "metadata": {"matchId": mid},
        "info": {"participants": [
            {"participantId": 1, "puuid": "p1", "teamId": 100,
             "teamPosition": position, "championName": "Ahri"},
            {"participantId": 2, "puuid": "opp", "teamId": 200,
             "teamPosition": "MIDDLE", "championName": "Zed"},
        ]},
    }


def _store_timeline(override_db, mid="m1"):
    from modules.data.timeline import compact_timeline

    override_db._cols["timelines"] = FakeCol([compact_timeline(_raw_timeline(mid))])


def test_match_timeline_returns_series(client, override_db):
    override_db._cols["player_matches"] = FakeCol([
        {"player_puuid": "p1", "matchId": "m1"},
    ])
    _set_raw_match(override_db, _timeline_match())
    _store_timeline(override_db)
    r = client.get("/players/p1/matches/m1/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["matchId"] == "m1"
    assert body["puuid"] == "p1"
    assert body["frameIntervalMs"] == 60000
    assert len(body["series"]) == 23
    assert body["series"][10] == {"minute": 10, "gold": 4500, "cs": 50, "xp": 1000, "level": 1}
    assert body["opponent"] == {"puuid": "opp", "championName": "Zed"}
    assert body["opponentSeries"][10]["cs"] == 40
    assert body["diff"][10] == {"minute": 10, "goldDiff": 1000, "csDiff": 10}
    assert body["milestones"]["goldAt10"] == 4500
    assert body["milestones"]["csAt10"] == 50
    assert body["milestones"]["goldDiffAt10"] == 1000


def test_match_timeline_player_match_not_found(client, override_db):
    _store_timeline(override_db)
    r = client.get("/players/nobody/matches/m1/timeline")
    assert r.status_code == 404
    assert r.json()["detail"] == "player_match not found"


def test_match_timeline_not_stored_404(client, override_db):
    override_db._cols["player_matches"] = FakeCol([
        {"player_puuid": "p1", "matchId": "m1"},
    ])
    r = client.get("/players/p1/matches/m1/timeline")
    assert r.status_code == 404
    assert "no timeline stored" in r.json()["detail"]


def test_match_timeline_without_opponent(client, override_db):
    override_db._cols["player_matches"] = FakeCol([
        {"player_puuid": "p1", "matchId": "m1"},
    ])
    _set_raw_match(override_db, _timeline_match(position=""))
    _store_timeline(override_db)
    r = client.get("/players/p1/matches/m1/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["series"][10]["cs"] == 50
    assert body["opponent"] is None
    assert body["opponentSeries"] == []
    assert body["diff"] == []


def test_match_composition_not_found(client):
    r = client.get("/matches/nope/composition")
    assert r.status_code == 404


def test_match_composition(client, override_db):
    match = {"metadata": {"matchId": "m1"}, "info": {"participants": [
        {"teamId": 100, "championName": "Garen"},
        {"teamId": 100, "championName": "Lux"},
        {"teamId": 200, "championName": "Jinx"},
    ]}}
    override_db._cols["matches"] = FakeCol([match])
    r = client.get("/matches/m1/composition")
    assert r.status_code == 200
    # JSON object keys are always strings, even when the source dict used ints.
    assert r.json() == {"100": ["Garen", "Lux"], "200": ["Jinx"]}


def test_ingest_player_validates_riotid(client):
    with patch("app.main.ingest_player", side_effect=ValueError("riotid must be in the form Name#Tagline")):
        r = client.post("/ingest/player", json={"riotid": "nohash"})
    assert r.status_code == 400


def test_ingest_player_invokes_core(client):
    with patch("app.main.ingest_player") as mock_ingest:
        mock_ingest.return_value = {"puuid": "p1", "matches_saved": 3}
        r = client.post("/ingest/player", json={
            "riotid": "TR Terminator#1998", "count": 5,
            "team_puuids": ["t1", "t2", "t3", "t4", "t5"],
        })
    assert r.status_code == 200
    _, kwargs = mock_ingest.call_args
    assert kwargs["riotid"] == "TR Terminator#1998"
    assert kwargs["min_team_members"] == 5
    assert r.json()["matches_saved"] == 3


def test_ingest_team_resolves_puuids_and_loops(client):
    team = [
        {"riotid": "TR A#T1"},
        {"riotid": "TR B#T2"},
        {"riotid": None},  # skipped
    ]
    with patch("app.main.get_team", return_value=team), \
         patch("app.main.resolve_team_puuids", return_value=["p-a", "p-b"]), \
         patch("app.main.RiotClient") as mock_client_cls, \
         patch("app.main.ingest_player", return_value={"matches_saved": 1}) as mock_ingest:
        r = client.post("/ingest/team", json={"count": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["team_puuids_resolved"] == 2
    assert len(body["players"]) == 2
    _, kwargs = mock_ingest.call_args
    assert kwargs["team_puuids"] == ["p-a", "p-b"]
    assert kwargs["min_team_members"] == 5


def test_coach_wires_ask_coach(client):
    with patch("scripts.ask_coach.ask_coach", return_value="Consejo de coach") as mock_ask:
        r = client.post("/coach", json={"question": "¿Qué mejoro?", "role": "Top"})
    assert r.status_code == 200
    assert r.json()["response"] == "Consejo de coach"
    assert mock_ask.call_args.kwargs["role"] == "Top"


def test_embeddings_query_requires_query_field(client):
    # Missing required `query` field -> pydantic validation error.
    r = client.post("/embeddings/query", json={"top_k": 5})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
#  gold endpoints
# ---------------------------------------------------------------------------

class FakeGoldItemClient:
    def resolve_version(self, game_version):
        return "14.10.1"

    def get_items_by_ids(self, ids, version=None):
        return {}


def _set_raw_match(override_db, match):
    override_db._cols["matches"] = FakeCol([match])


def _gold_match(mid="m1"):
    return {
        "metadata": {"matchId": mid},
        "info": {
            "gameVersion": "14.10.1",
            "participants": [
                {"puuid": "p1", "summonerName": "A", "teamId": 100, "teamPosition": "MID",
                 "goldEarned": 12000, "goldSpent": 11500, "itemsPurchased": 10,
                 "consumablesPurchased": 2, "win": True, "item0": 1001, "item1": 1055,
                 "timestamp": 1700000000000, "championName": "Ahri",
                 "challenges": {"goldPerMinute": 420}},
            ],
        },
    }


def test_player_gold_matches_returns_rows(client, override_db):
    override_db._cols["player_matches"] = FakeCol([
        {"player_puuid": "p1", "matchId": "m1", "role": "MID"},
    ])
    _set_raw_match(override_db, _gold_match())
    with patch("modules.data.gold_analysis._get_item_client", return_value=FakeGoldItemClient()):
        r = client.get("/players/p1/gold/matches")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["matchId"] == "m1"
    assert body[0]["goldEarned"] == 12000
    assert body[0]["gold_diff"] == 500


def test_player_gold_report_aggregates(client, override_db):
    override_db._cols["player_matches"] = FakeCol([
        {"player_puuid": "p1", "matchId": "m1", "role": "MID"},
        {"player_puuid": "p1", "matchId": "m2", "role": "MID"},
    ])
    _set_raw_match(override_db, _gold_match())
    override_db._cols["matches"].docs.append(_gold_match("m2"))
    with patch("modules.data.gold_analysis._get_item_client", return_value=FakeGoldItemClient()):
        r = client.get("/players/p1/gold/report")
    assert r.status_code == 200
    body = r.json()
    assert body["games_analyzed"] == 2
    assert body["wins"] == 2
    assert body["goldEarned"] == 12000  # mean


def test_player_gold_report_empty_404(client):
    r = client.get("/players/nobody/gold/report")
    assert r.status_code == 404


def test_match_gold_returns_participants(client, override_db):
    _set_raw_match(override_db, _gold_match())
    with patch("modules.data.gold_analysis._get_item_client", return_value=FakeGoldItemClient()):
        r = client.get("/matches/m1/gold")
    assert r.status_code == 200
    body = r.json()
    assert body["matchId"] == "m1"
    assert len(body["players"]) == 1
    assert body["players"][0]["goldEarned"] == 12000


def test_match_gold_not_found(client):
    r = client.get("/matches/nope/gold")
    assert r.status_code == 404


def test_gold_validation_limits_limit(client):
    r = client.get("/players/p1/gold/matches", params={"limit": 0})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
#  auth + hardening
# ---------------------------------------------------------------------------

def test_api_auth_rejects_without_key(client, monkeypatch):
    monkeypatch.setattr("app.main.API_TOKEN", "sekret")
    r = client.get("/team")
    assert r.status_code == 401
    r = client.post("/coach", json={"question": "hi"})
    assert r.status_code == 401


def test_api_auth_allows_with_correct_key(client, monkeypatch):
    monkeypatch.setattr("app.main.API_TOKEN", "sekret")
    with patch("app.main.get_team", return_value=[]):
        r = client.get("/team", headers={"X-API-Key": "sekret"})
    assert r.status_code == 200


def test_health_and_root_stay_public_with_auth(client, monkeypatch):
    monkeypatch.setattr("app.main.API_TOKEN", "sekret")
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_health_returns_503_when_db_down(client, override_db):
    override_db.list_collection_names = lambda: (_ for _ in ()).throw(
        RuntimeError("mongo down")
    )
    r = client.get("/health")
    assert r.status_code == 503


def test_team_path_traversal_rejected(client):
    r = client.get("/team", params={"team_path": "../etc/passwd"})
    assert r.status_code == 400
    r = client.post("/ingest/team", json={"team_path": "/etc/passwd"})
    assert r.status_code == 400


def test_ingest_team_missing_file_404(client):
    r = client.post("/ingest/team", json={"team_path": "nothere.json"})
    assert r.status_code == 404


def test_ingest_player_empty_team_puuids_rejected(client):
    r = client.post("/ingest/player", json={
        "riotid": "TR X#Y", "team_puuids": [],
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
#  pro baseline / comparison
# ---------------------------------------------------------------------------

def _support_matches():
    return [
        {"player_puuid": "p1", "matchId": "m1", "role": "Support",
         "championName": "Thresh",
         "parsed_metrics": {"kills": 2.0, "deaths": 3.0, "assists": 12.0,
                            "kda": 4.667, "visionScorePerMinute": 1.62}},
    ]


def _support_baseline():
    return {
        "role": "Support", "source": "oracles_elixir", "games": 4820,
        "season": 2025,
        "metrics": {
            "kda": {"mean": 3.0, "median": 3.1, "p25": 2.4, "p75": 3.8, "n": 4820},
            "visionScorePerMinute": {"mean": 2.21, "median": 2.14,
                                     "p25": 1.72, "p75": 2.63, "n": 4820},
        },
    }


def _mid_baseline():
    return {
        "role": "Mid", "source": "oracles_elixir", "games": 100,
        "metrics": {
            "kda": {"mean": 3.5, "median": 3.6, "p25": 2.9, "p75": 4.2, "n": 100},
        },
    }


def test_player_comparison_enriches_rows_with_percentiles(client, override_db):
    override_db._cols["player_matches"] = FakeCol(_support_matches())
    override_db._cols["pro_baselines"] = FakeCol([_support_baseline()])
    with patch("modules.data.report_builder.ReportBuilder.save_report"):
        r = client.get("/players/p1/comparison")
    assert r.status_code == 200
    body = r.json()
    assert body["player"] == "p1"
    assert body["role"] == "Support"
    assert body["games_analyzed"] == 1
    assert body["baseline"] == {
        "role": "Support", "source": "oracles_elixir", "games": 4820,
        "season": 2025,
    }
    rows = {row["metric"]: row for row in body["rows"]}
    vision = rows["visionScorePerMinute"]
    assert vision["player"] == 1.62
    assert vision["pro"] == 2.21
    assert vision["delta"] == -0.59
    assert vision["pct"] == -26.7
    assert vision["p25"] == 1.72
    assert vision["median"] == 2.14
    assert vision["p75"] == 2.63
    assert vision["n"] == 4820


def test_player_comparison_without_baseline_is_empty_payload(client, override_db):
    override_db._cols["player_matches"] = FakeCol(_support_matches())
    with patch("modules.data.report_builder.ReportBuilder.save_report"):
        r = client.get("/players/p1/comparison")
    assert r.status_code == 200
    body = r.json()
    assert body["baseline"] is None
    assert body["rows"] == []
    assert body["role"] == "Support"


def test_player_comparison_no_matches_404(client):
    r = client.get("/players/nobody/comparison")
    assert r.status_code == 404


def test_player_comparison_role_override(client, override_db):
    override_db._cols["player_matches"] = FakeCol(_support_matches())
    override_db._cols["pro_baselines"] = FakeCol([
        _support_baseline(), _mid_baseline(),
    ])
    with patch("modules.data.report_builder.ReportBuilder.save_report"):
        r = client.get("/players/p1/comparison", params={"role": "Mid"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "Mid"
    assert body["baseline"]["role"] == "Mid"
    kda = next(row for row in body["rows"] if row["metric"] == "kda")
    assert kda["pro"] == 3.5
    assert kda["median"] == 3.6


def test_player_report_carries_pro_reference(client, override_db):
    override_db._cols["player_matches"] = FakeCol(_support_matches())
    override_db._cols["pro_baselines"] = FakeCol([_support_baseline()])
    with patch("modules.data.report_builder.ReportBuilder.save_report"):
        r = client.get("/players/p1/report")
    assert r.status_code == 200
    body = r.json()
    assert body["pro_reference"] == {"kda": 3.0, "visionScorePerMinute": 2.21}
    assert body["deltas"]["kda"] == 1.667


def test_pro_baseline_returns_doc(client, override_db):
    override_db._cols["pro_baselines"] = FakeCol([_support_baseline()])
    r = client.get("/pro/baseline/Support")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "Support"
    assert body["source"] == "oracles_elixir"
    assert body["games"] == 4820
    assert body["season"] == 2025
    assert body["metrics"]["kda"]["median"] == 3.1


def test_pro_baseline_missing_404(client):
    r = client.get("/pro/baseline/Top")
    assert r.status_code == 404
