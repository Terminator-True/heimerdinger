"""Verify the anonymized Riot fixtures replay through RiotClient via respx.

Proves the fixture payloads (account, match ids, full match) are valid and
mounted hermetically — the "no live Riot" guarantee behind the snapshots.
"""
from modules.riot_api.client import RiotClient


def test_account_fixture_replays(riot_router):
    client = RiotClient(api_key="fake-key")
    acct = client.get_account_by_riot_id("Anon Player", "ANON")
    assert acct["puuid"] == "synthetic-puuid-0001"
    assert acct["gameName"] == "Anon Player"


def test_match_ids_fixture_replays(riot_router):
    client = RiotClient(api_key="fake-key")
    ids = client.get_match_ids_by_puuid("synthetic-puuid-0001")
    assert ids == ["ANON-MATCH-0001"]


def test_match_fixture_replays(riot_router):
    client = RiotClient(api_key="fake-key")
    m = client.get_match_by_id("ANON-MATCH-0001")
    assert m["metadata"]["matchId"] == "ANON-MATCH-0001"
    assert len(m["info"]["participants"]) == 10
