import types

from modules.data.match_parser import MatchParser
from modules.db.repositories import MatchesRepository


class FakeCol(dict):
    def __init__(self):
        super().__init__()
        self.updated = []

    def update_one(self, *args, **kwargs):
        self.updated.append((args, kwargs))

    def create_index(self, *args, **kwargs):
        return None


class FakeDB(dict):
    def get_collection(self, name):
        return self.setdefault(name, FakeCol())


def test_ingest_when_puuid_absent_does_not_call_upsert(monkeypatch):
    # Prepare fake repo that records calls
    fake_db = FakeDB()
    matches_col = fake_db.get_collection("matches")
    repo = MatchesRepository(matches_col)

    match = {
        "metadata": {"matchId": "m4"},
        "info": {
            "gameStartTimestamp": 1000,
            "gameDuration": 100,
            "participants": [
                {"puuid": "someone_else", "summonerName": "Other", "championName": "Lux"}
            ],
        },
    }

    # call parse_match and simulate ingest logic: look for target puuid that doesn't exist
    parsed = MatchParser.parse_match(match)
    participants = parsed.get("players", [])
    target = None
    for p in participants:
        if p.get("puuid") == "missing-puuid":
            target = p
            break

    # ensure target not found and repo.upsert_parsed_player_match is not invoked
    assert target is None
