import os
from typing import List, Optional

import httpx
import urllib.parse
from dotenv import load_dotenv

load_dotenv()


class RiotClient:
    def __init__(self, region: str = "europe", api_key: Optional[str] = None):
        """
        Riot API client.

        Notes:
        - api_key may be provided explicitly (useful for tests); if omitted
          the client will attempt to read RIOT_API_KEY from the environment.
        - Do NOT raise at import time if the key is missing. Tests and some
          environments may want to instantiate the client without a real key
          and rely on HTTP mocking instead.
        """
        self.base = f"https://{region}.api.riotgames.com"
        key = api_key or os.getenv("RIOT_API_KEY")
        headers = {"X-Riot-Token": key} if key else {}
        self.client = httpx.Client(headers=headers, timeout=10.0)

    def get_summoner_by_name(self, name: str) -> dict:
        url = f"{self.base}/lol/summoner/v4/summoners/by-name/{name}"
        # Ensure we pass an httpx.URL or str to httpx to avoid transport-level
        # internals returning tuple/bytes to respx in some environments.
        r = self.client.get(url)
        r.raise_for_status()
        return r.json()

    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict:
        """Get account by Riot ID: gameName and tagLine.

        The Riot Accounts endpoint expects the tagLine without a leading '#'.
        Both segments must be URL-encoded.
        """
        # strip leading # from tag_line if present
        clean_tag = tag_line.lstrip("#")
        q_name = urllib.parse.quote(game_name, safe="")
        q_tag = urllib.parse.quote(clean_tag, safe="")
        url = f"{self.base}/riot/account/v1/accounts/by-riot-id/{q_name}/{q_tag}"
        r = self.client.get(url)
        r.raise_for_status()
        return r.json()

    def get_match_ids_by_puuid(self, puuid: str, count: int = 20, start: int = 0, region_rep: str = "europe") -> List[str]:
        # match-v5 uses regional routing (e.g., europe, americas)
        url = f"https://{region_rep}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
        r = self.client.get(url)
        r.raise_for_status()
        return r.json()

    def get_match_by_id(self, match_id: str, region_rep: str = "europe") -> dict:
        url = f"https://{region_rep}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        r = self.client.get(url)
        r.raise_for_status()
        return r.json()
