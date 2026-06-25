import respx
import httpx
from modules.riot_api.client import RiotClient


def test_get_match_ids_by_puuid():
    client = RiotClient(api_key="fake-key")
    puuid = "puuid-123"
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=5"

    with respx.mock as rsps:
        rsps.get(url).respond(200, json=["match1", "match2"])
        ids = client.get_match_ids_by_puuid(puuid, count=5)
        assert ids == ["match1", "match2"]


def test_get_match_by_id():
    client = RiotClient(api_key="fake-key")
    match_id = "match1"
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"

    with respx.mock as rsps:
        rsps.get(url).respond(200, json={"metadata": {"matchId": match_id}})
        m = client.get_match_by_id(match_id)
        assert m["metadata"]["matchId"] == match_id


def test_get_account_by_riot_id():
    client = RiotClient(api_key="fake-key", region="europe")
    name = "TR Terminator"
    tagline = "#1998"
    qname = "TR%20Terminator"
    qtag = "1998"
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{qname}/{qtag}"

    with respx.mock as rsps:
        rsps.get(url).respond(200, json={"puuid": "puuid-xyz"})
        acct = client.get_account_by_riot_id(name, tagline)
        assert acct["puuid"] == "puuid-xyz"
