"""Fixtures for the Hito 0 equivalence harness.

`riot_router` mounts the anonymized Riot fixtures under tests/fixtures/riot/
onto a respx router so RiotClient calls replay deterministically with no live
network. Same pattern as tests/test_riot_client.py.
"""
import json
import urllib.parse
from pathlib import Path

import pytest
import respx

FIXTURE_DIR = Path(__file__).resolve().parent / "riot"
BASE_ACCOUNT = "https://europe.api.riotgames.com"
BASE_MATCH = "https://europe.api.riotgames.com"


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def riot_router():
    """Mount anonymized Riot fixtures; yields the active respx router."""
    account = _load("account.json")
    match_ids = _load("match_ids.json")
    match_id = match_ids[0]
    match_doc = _load(f"match_{match_id}.json")
    puuid = account["puuid"]

    game_name = account.get("gameName", "")
    tag_line = account.get("tagLine", "")
    q_name = urllib.parse.quote(game_name, safe="")
    q_tag = urllib.parse.quote(tag_line.lstrip("#"), safe="")

    account_url = f"{BASE_ACCOUNT}/riot/account/v1/accounts/by-riot-id/{q_name}/{q_tag}"
    ids_url = f"{BASE_MATCH}/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=20"
    match_url = f"{BASE_MATCH}/lol/match/v5/matches/{match_id}"

    with respx.mock as router:
        router.get(account_url).respond(200, json=account)
        router.get(ids_url).respond(200, json=match_ids)
        router.get(match_url).respond(200, json=match_doc)
        yield router
