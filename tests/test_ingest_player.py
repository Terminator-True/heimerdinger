"""Tests for ingest_player — dual check, error logging, extended return."""

from unittest.mock import patch, MagicMock
from modules.ingest.lib import ingest_player


class FakeMatchesRepo:
    def __init__(self):
        self.matches = set()
        self.player_matches = set()

    def match_exists(self, mid):
        return mid in self.matches

    def player_match_exists(self, mid, puuid):
        return (mid, puuid) in self.player_matches

    def upsert_match(self, m):
        self.matches.add(m.get("metadata", {}).get("matchId"))
        return True

    def upsert_parsed_player_match(self, pp):
        self.player_matches.add((pp["matchId"], pp["player_puuid"]))


def _make_client_and_match_ids(match_ids):
    client = MagicMock()
    client.get_match_ids_by_puuid.return_value = match_ids
    client.get_account_by_riot_id.return_value = {"puuid": "test-puuid"}
    return client


def _make_match_json(mid, puuid="test-puuid"):
    return {
        "metadata": {"matchId": mid},
        "info": {
            "gameDuration": 600,
            "participants": [
                {
                    "puuid": puuid,
                    "championName": "Ahri",
                    "champion": "Ahri",
                    "kills": 5, "deaths": 2, "assists": 3,
                    "totalMinionsKilled": 100,
                    "goldEarned": 8000,
                    "visionScore": 15,
                    "totalDamageDealtToChampions": 12000,
                    "teamId": 100,
                    "win": True,
                }
            ],
        },
    }


def _make_participant(puuid):
    return {"puuid": puuid, "championName": "Ahri", "role": "MID"}


def _wire_parser(mock_parser, participants):
    parser_instance = MagicMock()
    mock_parser.parse_match.return_value = parser_instance
    parser_instance.get.return_value = participants
    return parser_instance


@patch("modules.ingest.lib.get_db")
@patch("modules.ingest.lib.MatchesRepository")
@patch("modules.ingest.lib.RiotClient")
@patch("modules.ingest.lib.TokenBucketLimiter")
@patch("modules.ingest.lib.MatchParser")
def test_ingest_player_discards_when_team_below_presence(mock_parser, mock_limiter,
                                                         mock_client_cls, mock_repo_cls,
                                                         mock_get_db):
    """Match with fewer than min_team_members present is discarded (not saved)."""
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_db.get_collection.return_value = mock_col
    mock_get_db.return_value = mock_db

    repo = FakeMatchesRepo()
    mock_repo_cls.return_value = repo

    client = _make_client_and_match_ids(["mid-1"])
    client.get_match_by_id.side_effect = lambda mid, region_rep=None: _make_match_json(mid)
    mock_client_cls.return_value = client

    # Only 2 of the 5 team members are present in this match.
    _wire_parser(mock_parser, [_make_participant("test-puuid"), _make_participant("team-2")])

    result = ingest_player(
        "Player#Tag1", count=5, region="europe",
        team_puuids=["team-1", "team-2", "team-3", "team-4", "team-5"],
        min_team_members=5,
    )

    assert result["matches_discarded"] == 1
    assert result["matches_saved"] == 0
    # Match must NOT be saved to the matches or player_matches collections.
    assert "mid-1" not in repo.matches
    assert repo.player_matches == set()


@patch("modules.ingest.lib.get_db")
@patch("modules.ingest.lib.MatchesRepository")
@patch("modules.ingest.lib.RiotClient")
@patch("modules.ingest.lib.TokenBucketLimiter")
@patch("modules.ingest.lib.MatchParser")
def test_ingest_player_saves_when_team_present(mock_parser, mock_limiter,
                                               mock_client_cls, mock_repo_cls,
                                               mock_get_db):
    """Match is ingested when the full team (5 members) is present."""
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_db.get_collection.return_value = mock_col
    mock_get_db.return_value = mock_db

    repo = FakeMatchesRepo()
    mock_repo_cls.return_value = repo

    client = _make_client_and_match_ids(["mid-1"])
    client.get_match_by_id.side_effect = lambda mid, region_rep=None: _make_match_json(mid)
    mock_client_cls.return_value = client

    # All 5 team members are present, including the target player.
    _wire_parser(mock_parser, [_make_participant(p) for p in
                               ("test-puuid", "team-2", "team-3", "team-4", "team-5")])

    result = ingest_player(
        "Player#Tag1", count=5, region="europe",
        team_puuids=["test-puuid", "team-2", "team-3", "team-4", "team-5"],
        min_team_members=5,
    )

    assert result["matches_discarded"] == 0
    assert result["matches_saved"] == 1
    assert "mid-1" in repo.matches


@patch("modules.ingest.lib.get_db")
@patch("modules.ingest.lib.MatchesRepository")
@patch("modules.ingest.lib.RiotClient")
@patch("modules.ingest.lib.TokenBucketLimiter")
@patch("modules.ingest.lib.MatchParser")
def test_ingest_player_parse_error_stores_raw_match(mock_parser, mock_limiter,
                                                    mock_client_cls, mock_repo_cls,
                                                    mock_get_db):
    """When parsing fails, the raw match is still stored (dual-check depends
    on it) but no player metrics are saved."""
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_db.get_collection.return_value = mock_col
    mock_get_db.return_value = mock_db

    repo = FakeMatchesRepo()
    mock_repo_cls.return_value = repo

    client = _make_client_and_match_ids(["mid-bad"])
    client.get_match_by_id.side_effect = lambda mid, region_rep=None: _make_match_json(mid)
    mock_client_cls.return_value = client

    mock_parser.parse_match.side_effect = ValueError("boom")

    result = ingest_player("Player#Tag1", count=5, region="europe")

    assert result["matches_parse_errors"] == 1
    assert result["matches_saved"] == 0
    # Raw match is persisted so the dual-check short-circuits next run.
    assert "mid-bad" in repo.matches
    assert repo.player_matches == set()


@patch("modules.ingest.lib.get_db")
@patch("modules.ingest.lib.MatchesRepository")
@patch("modules.ingest.lib.RiotClient")
@patch("modules.ingest.lib.TokenBucketLimiter")
@patch("modules.ingest.lib.MatchParser")
def test_ingest_player_partial_team_resolution_raises(mock_parser, mock_limiter,
                                                      mock_client_cls, mock_repo_cls,
                                                      mock_get_db):
    """Fewer team puuids than min_team_members fails loudly, not silently."""
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_db.get_collection.return_value = mock_col
    mock_get_db.return_value = mock_db

    mock_repo_cls.return_value = FakeMatchesRepo()
    mock_client_cls.return_value = _make_client_and_match_ids(["mid-1"])

    import pytest

    with pytest.raises(
        RuntimeError, match="Only 3/5 team puuids resolved"
    ):
        ingest_player(
            "Player#Tag1", count=5, region="europe",
            team_puuids=["t1", "t2", "t3"],
            min_team_members=5,
        )


@patch("modules.ingest.lib.get_db")
@patch("modules.ingest.lib.MatchesRepository")
@patch("modules.ingest.lib.RiotClient")
@patch("modules.ingest.lib.TokenBucketLimiter")
@patch("modules.ingest.lib.MatchParser")
def test_ingest_player_skips_when_both_exist(mock_parser, mock_limiter, mock_client_cls,
                                             mock_repo_cls, mock_get_db):
    """When match exists in BOTH matches AND player_matches, skip it."""
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_db.get_collection.return_value = mock_col
    mock_get_db.return_value = mock_db

    repo = FakeMatchesRepo()
    mock_repo_cls.return_value = repo

    client = _make_client_and_match_ids(["mid-1"])
    mock_client_cls.return_value = client

    # Pre-mark mid-1 as existing in BOTH collections
    repo.matches.add("mid-1")
    repo.player_matches.add(("mid-1", "test-puuid"))

    result = ingest_player("Player#Tag1", count=5, region="europe")

    assert result["matches_fetched"] == 1
    # mid-1 is in BOTH collections → skip it
    assert result["matches_skipped"] == 1
    assert result["matches_saved"] == 0


@patch("modules.ingest.lib.get_db")
@patch("modules.ingest.lib.MatchesRepository")
@patch("modules.ingest.lib.RiotClient")
@patch("modules.ingest.lib.TokenBucketLimiter")
@patch("modules.ingest.lib.MatchParser")
def test_ingest_player_fetches_when_only_match_exists(mock_parser, mock_limiter,
                                                       mock_client_cls, mock_repo_cls,
                                                       mock_get_db):
    """When match exists ONLY in matches (not player_matches), still fetch."""
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_db.get_collection.return_value = mock_col
    mock_get_db.return_value = mock_db

    repo = FakeMatchesRepo()
    mock_repo_cls.return_value = repo

    mid = "mid-needs-player"
    client = _make_client_and_match_ids([mid])
    mock_client_cls.return_value = client

    # Mark match as existing in `matches` collection only
    repo.matches.add(mid)

    def fake_get_match_by_id(mid, region_rep=None):
        return _make_match_json(mid)

    client.get_match_by_id.side_effect = fake_get_match_by_id

    mock_parser_instance = MagicMock()
    mock_parser.parse_match.return_value = mock_parser_instance
    mock_parser_instance.get.return_value = [
        {"puuid": "test-puuid", "championName": "Ahri", "role": "MID"}
    ]

    result = ingest_player("Player#Tag1", count=5, region="europe")

    assert result["matches_fetched"] == 1
    # Should NOT be skipped
    assert result["matches_skipped"] == 0
    # Should be saved
    assert result["matches_saved"] == 1


@patch("modules.ingest.lib.get_db")
@patch("modules.ingest.lib.MatchesRepository")
@patch("modules.ingest.lib.RiotClient")
@patch("modules.ingest.lib.TokenBucketLimiter")
@patch("modules.ingest.lib.MatchParser")
def test_ingest_player_extended_return_keys(mock_parser, mock_limiter, mock_client_cls,
                                             mock_repo_cls, mock_get_db):
    """Return dict includes all new counters."""
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_db.get_collection.return_value = mock_col
    mock_get_db.return_value = mock_db

    repo = FakeMatchesRepo()
    mock_repo_cls.return_value = repo

    client = _make_client_and_match_ids(["m1", "m2"])
    mock_client_cls.return_value = client

    def fake_get_match_by_id(mid, region_rep=None):
        return _make_match_json(mid)

    client.get_match_by_id.side_effect = fake_get_match_by_id

    mock_parser_instance = MagicMock()
    mock_parser.parse_match.return_value = mock_parser_instance
    mock_parser_instance.get.return_value = [
        {"puuid": "test-puuid", "championName": "Ahri", "role": "MID"}
    ]

    result = ingest_player("Player#Tag1", count=5, region="europe")

    assert "matches_skipped" in result
    assert "matches_discarded" in result
    assert "matches_parse_errors" in result
    assert "matches_fetch_errors" in result
    assert "matches_fetched" in result
    assert "matches_saved" in result
