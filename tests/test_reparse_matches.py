"""Tests for scripts.reparse_matches — offline enrichment of player_matches."""

from scripts.reparse_matches import reparse_player


class FakeCollection:
    """Dict-backed fake collection (docs are plain dicts in a list)."""

    def __init__(self, db):
        self._db = db
        self.docs = []

    @property
    def database(self):
        return self._db

    def get_collection(self, name):
        return self._db.get_collection(name)

    def create_index(self, *args, **kwargs):
        return None

    def insert(self, doc):
        self.docs.append(doc)

    def find(self, query):
        return [d for d in self.docs if self._matches(d, query)]

    def find_one(self, query):
        for d in self.docs:
            if self._matches(d, query):
                return d
        return None

    def update_one(self, filter_q, update_q, upsert=False):
        for d in self.docs:
            if self._matches(d, filter_q):
                d.update(update_q.get("$set", {}))
                return
        if upsert:
            doc = dict(update_q.get("$set", {}))
            doc.update(update_q.get("$setOnInsert", {}))
            self.docs.append(doc)

    @staticmethod
    def _matches(doc, query):
        return all(doc.get(k) == v for k, v in query.items())


class FakeDB:
    def __init__(self):
        self._cols = {}

    def get_collection(self, name):
        return self._cols.setdefault(name, FakeCollection(self))


def _match_doc(mid, puuid="p1"):
    return {
        "metadata": {"matchId": mid},
        "info": {
            "gameDuration": 1800,
            "participants": [
                {
                    "puuid": puuid,
                    "championName": "Thresh",
                    "kills": 2, "deaths": 4, "assists": 18,
                    "totalMinionsKilled": 30,
                    "goldEarned": 9000,
                    "visionScore": 55,
                    "totalDamageDealtToChampions": 8000,
                    "teamId": 100,
                    "win": True,
                    "challenges": {
                        "killParticipation": 0.72,
                        "visionScorePerMinute": 1.83,
                        "controlWardsPlaced": 4,
                    },
                }
            ],
        },
    }


def _seed_existing(db, mid, puuid="p1"):
    """An old-style player_matches doc with only parser fields."""
    db.get_collection("player_matches").insert({
        "player_puuid": puuid,
        "matchId": mid,
        "parsed_metrics": {"cs_per_min": 7.5, "kda": 3.0, "cs": 150},
        "championName": "Thresh",
        "role": "UTILITY",
        "timestamp": 1700000000000,
    })


def test_reparse_enriches_and_preserves_parser_fields():
    db = FakeDB()
    db.get_collection("matches").insert(_match_doc("m1"))
    _seed_existing(db, "m1")

    summary = reparse_player(db, "p1")

    assert summary["scanned"] == 1
    assert summary["enriched"] == 1
    assert summary["skipped"] == 0
    assert summary["errors"] == 0
    assert "ch_killParticipation" in summary["sample_new_keys"]

    stored = db.get_collection("player_matches").find_one(
        {"player_puuid": "p1", "matchId": "m1"})
    metrics = stored["parsed_metrics"]
    # Rich metrics merged in...
    assert metrics["ch_killParticipation"] == 0.72
    assert metrics["ch_visionScorePerMinute"] == 1.83
    # ...without losing the parser's normalized fields.
    assert metrics["cs_per_min"] == 7.5
    assert metrics["kda"] == 3.0
    assert metrics["cs"] == 150


def test_reparse_skips_matches_without_participant():
    db = FakeDB()
    db.get_collection("matches").insert(_match_doc("m1", puuid="someone-else"))

    summary = reparse_player(db, "p1")

    assert summary["scanned"] == 1
    assert summary["enriched"] == 0
    assert summary["skipped"] == 1
    # No player_matches doc is created for a match the player is not in.
    assert db.get_collection("player_matches").docs == []


def test_reparse_dry_run_writes_nothing():
    db = FakeDB()
    db.get_collection("matches").insert(_match_doc("m1"))
    _seed_existing(db, "m1")

    summary = reparse_player(db, "p1", dry_run=True)

    assert summary["enriched"] == 1
    assert summary["sample_new_keys"]  # would-be changes are reported
    stored = db.get_collection("player_matches").find_one(
        {"player_puuid": "p1", "matchId": "m1"})
    # Untouched: still only the parser fields.
    assert stored["parsed_metrics"] == {"cs_per_min": 7.5, "kda": 3.0, "cs": 150}


def test_reparse_respects_limit():
    db = FakeDB()
    for i in range(5):
        db.get_collection("matches").insert(_match_doc(f"m{i}"))
        _seed_existing(db, f"m{i}")

    summary = reparse_player(db, "p1", limit=2)

    assert summary["scanned"] == 2
    assert summary["enriched"] == 2
