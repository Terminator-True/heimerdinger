"""Tests for MatchesRepository — player_match_exists and index logging."""

from modules.db.repositories import MatchesRepository


def _get_nested(doc, dotted_key):
    """Resolve a dotted key like 'metadata.matchId' in a nested dict."""
    parts = dotted_key.split(".")
    current = doc
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


class FakeCol:
    """Minimal dict-backed fake for a MongoDB collection."""

    def __init__(self):
        self.docs = {}
        self.index_calls = []

    def count_documents(self, query, limit=None):
        for doc in self.docs.values():
            match = True
            for k, v in query.items():
                val = _get_nested(doc, k)
                if val != v:
                    match = False
                    break
            if match:
                return 1
        return 0

    def find_one(self, query):
        for doc in self.docs.values():
            match = True
            for k, v in query.items():
                val = _get_nested(doc, k)
                if val != v:
                    match = False
                    break
            if match:
                return doc
        return None

    def update_one(self, filter_q, update_q, upsert=False):
        key = _get_nested(filter_q, "metadata.matchId")
        if key and key in self.docs:
            self.docs[key].update(update_q.get("$set", {}))
        elif key and upsert:
            self.docs[key] = update_q.get("$set", {})

    def create_index(self, keys, unique=False):
        self.index_calls.append((keys, unique))


class FakeColWithIndexError(FakeCol):
    """Fake collection that raises on create_index."""

    def create_index(self, keys, unique=False):
        raise RuntimeError("Index creation failed: E11000")


def test_player_match_exists_returns_true():
    col = FakeCol()
    col.docs["m1"] = {"player_puuid": "puuid-X", "matchId": "m1"}
    repo = MatchesRepository(col)
    # Manually wire the _player_matches reference
    repo._player_matches = col

    assert repo.player_match_exists("m1", "puuid-X") is True


def test_player_match_exists_returns_false():
    col = FakeCol()
    col.docs["m1"] = {"player_puuid": "puuid-Y", "matchId": "m1"}
    repo = MatchesRepository(col)
    repo._player_matches = col

    assert repo.player_match_exists("m1", "puuid-X") is False


def test_player_match_exists_empty_collection():
    col = FakeCol()
    repo = MatchesRepository(col)
    repo._player_matches = col

    assert repo.player_match_exists("m1", "puuid-X") is False


def test_match_exists_returns_true():
    col = FakeCol()
    col.docs["m1"] = {"metadata": {"matchId": "m1"}}
    repo = MatchesRepository(col)
    assert repo.match_exists("m1") is True


def test_match_exists_returns_false():
    col = FakeCol()
    repo = MatchesRepository(col)
    assert repo.match_exists("m1") is False
