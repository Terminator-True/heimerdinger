import datetime
try:
    import mongomock
except Exception:
    mongomock = None

from modules.data.match_parser import parse_match
from modules.db.repositories import MatchesRepository


class FakeCollection:
    """Very small dict-backed fake collection to simulate update_one with upsert."""

    def __init__(self):
        self.docs = {}
        self._db = self

    @property
    def database(self):
        return self

    def get_collection(self, name):
        # return self for simplicity; tests only call a single collection
        return self

    def create_index(self, *args, **kwargs):
        return None

    def update_one(self, filter_q, update_q, upsert=False):
        key = (filter_q.get("player_puuid"), filter_q.get("matchId"))
        if key in self.docs:
            # apply $set
            set_doc = update_q.get("$set", {})
            self.docs[key].update(set_doc)
        else:
            if upsert:
                doc = update_q.get("$set", {}).copy()
                # apply setOnInsert
                soi = update_q.get("$setOnInsert", {})
                doc.update(soi)
                self.docs[key] = doc


def test_upsert_parsed_player_match_integration():
    # Build a minimal fake match JSON with one participant
    fake_match = {
        "metadata": {"matchId": "M-1"},
        "info": {
            "gameStartTimestamp": int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000),
            "gameDuration": 1200,
            "participants": [
                {
                    "puuid": "player-123",
                    "summonerName": "Tester",
                    "championName": "Ahri",
                    "teamPosition": "MID",
                    "kills": 5,
                    "deaths": 2,
                    "assists": 3,
                    "totalMinionsKilled": 150,
                    "neutralMinionsKilled": 0,
                    "goldEarned": 10000,
                    "visionScore": 20,
                    "totalDamageDealtToChampions": 12000,
                    "teamId": 100,
                    "win": True,
                }
            ],
        },
    }

    parsed = parse_match(fake_match)
    players = parsed.get("players", [])
    assert len(players) == 1
    p = players[0]

    if mongomock:
        client = mongomock.MongoClient()
        db = client["testdb"]
        matches_col = db.get_collection("matches")
        repo = MatchesRepository(matches_col)
        player_parsed = {
            "player_puuid": p["puuid"],
            "matchId": fake_match["metadata"]["matchId"],
            "parsed_metrics": p,
            "championName": p.get("championName"),
            "role": p.get("role"),
            "timestamp": p.get("timestamp"),
        }
        # exercise the upsert
        repo.upsert_parsed_player_match(player_parsed)
        # verify in mongomock
        pm = db.get_collection("player_matches").find_one({"player_puuid": p["puuid"], "matchId": fake_match["metadata"]["matchId"]})
        assert pm is not None
        assert pm["parsed_metrics"]["championName"] == "Ahri"
    else:
        fake_col = FakeCollection()
        repo = MatchesRepository(fake_col)
        player_parsed = {
            "player_puuid": p["puuid"],
            "matchId": fake_match["metadata"]["matchId"],
            "parsed_metrics": p,
            "championName": p.get("championName"),
            "role": p.get("role"),
            "timestamp": p.get("timestamp"),
        }
        repo.upsert_parsed_player_match(player_parsed)
        key = (p["puuid"], fake_match["metadata"]["matchId"])
        assert key in fake_col.docs
        assert fake_col.docs[key]["parsed_metrics"]["championName"] == "Ahri"
