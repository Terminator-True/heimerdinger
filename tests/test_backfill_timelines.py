"""Tests for scripts.backfill_timelines — fetch/store timeline backfill."""

from scripts.backfill_timelines import backfill_player


class FakeCollection:
    """Dict-backed fake collection with the subset of pymongo we use."""

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

    def count_documents(self, query, limit=None):
        return sum(1 for d in self.docs if self._matches(d, query))

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


class FakeClient:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = set(fail_on or [])

    def get_match_timeline(self, match_id, region_rep="europe"):
        self.calls.append(match_id)
        if match_id in self.fail_on:
            raise RuntimeError("timeline boom")
        return _raw_timeline(match_id)


class NoopLimiter:
    def acquire(self):
        return True


def _raw_timeline(mid):
    return {
        "metadata": {"matchId": mid, "participants": ["p1"]},
        "info": {
            "frameInterval": 60000,
            "participants": [{"participantId": 1, "puuid": "p1"}],
            "frames": [{
                "timestamp": 0,
                "participantFrames": {"1": {"participantId": 1, "totalGold": 500,
                                            "minionsKilled": 0, "jungleMinionsKilled": 0,
                                            "xp": 0, "level": 1, "currentGold": 500}},
                "events": [{"type": "GAME_START"}],
            }],
        },
    }


def _seed_match(db, mid):
    db.get_collection("matches").insert({"metadata": {"matchId": mid}, "info": {}})


def _seed_player_match(db, mid, puuid="p1"):
    db.get_collection("player_matches").insert({"player_puuid": puuid, "matchId": mid})


def _seed_timeline(db, mid):
    db.get_collection("timelines").insert({"matchId": mid})


def test_backfill_skips_existing_and_stores_new():
    db = FakeDB()
    _seed_player_match(db, "m1")
    _seed_player_match(db, "m2")
    _seed_timeline(db, "m1")

    client = FakeClient()
    summary = backfill_player(db, "p1", client, limiter=NoopLimiter())

    assert summary["scanned"] == 2
    assert summary["skipped"] == 1  # m1 already has a timeline
    assert summary["fetched"] == 1
    assert summary["stored"] == 1
    assert summary["errors"] == 0

    # Only the missing one was fetched, and it is now stored compacted.
    assert client.calls == ["m2"]
    stored = db.get_collection("timelines").find_one({"matchId": "m2"})
    assert stored is not None
    assert "events" not in stored
    assert "events" not in stored["frames"][0]


def test_backfill_dry_run_writes_nothing():
    db = FakeDB()
    _seed_player_match(db, "m2")

    client = FakeClient()
    summary = backfill_player(db, "p1", client, dry_run=True, limiter=NoopLimiter())

    assert summary["scanned"] == 1
    assert summary["fetched"] == 1
    assert summary["stored"] == 0
    assert client.calls == []  # nothing fetched in dry-run
    assert db.get_collection("timelines").docs == []


def test_backfill_all_scans_matches_collection():
    db = FakeDB()
    _seed_match(db, "m1")
    _seed_match(db, "m2")

    client = FakeClient()
    summary = backfill_player(db, None, client, limiter=NoopLimiter())

    assert summary["scanned"] == 2
    assert summary["fetched"] == 2
    assert summary["stored"] == 2
    assert client.calls == ["m1", "m2"]


def test_backfill_counts_errors_and_continues():
    db = FakeDB()
    _seed_player_match(db, "m1")
    _seed_player_match(db, "m2")

    client = FakeClient(fail_on=["m1"])
    summary = backfill_player(db, "p1", client, limiter=NoopLimiter())

    assert summary["fetched"] == 2
    assert summary["stored"] == 1
    assert summary["errors"] == 1
    assert db.get_collection("timelines").find_one({"matchId": "m2"}) is not None


def test_backfill_respects_limit():
    db = FakeDB()
    for i in range(5):
        _seed_player_match(db, f"m{i}")

    client = FakeClient()
    summary = backfill_player(db, "p1", client, limit=2, limiter=NoopLimiter())

    assert summary["scanned"] == 2
    assert len(client.calls) == 2
