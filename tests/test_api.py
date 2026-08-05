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

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self.docs[:n]

    def find_one(self, filt):
        puuid = filt.get("player_puuid")
        match_id = filt.get("matchId")
        for d in self.docs:
            if puuid and d.get("player_puuid") != puuid:
                continue
            if match_id and d.get("matchId") != match_id:
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
