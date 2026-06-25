"""Core ingestion helpers for players and teams.

This module centralizes the logic used by CLI scripts to ingest player
match data into the database. The existing scripts should delegate to
functions here to avoid duplication.
"""
from typing import Dict, Any
from modules.db.connection import get_db
from modules.db.repositories import MatchesRepository
from modules.riot_api.client import RiotClient
from modules.riot_api.rate_limiter import TokenBucketLimiter
from modules.data.match_parser import MatchParser
from modules.logger import get_logger
import os

logger = get_logger(__name__)


def ingest_player(riotid: str, count: int = 5, region: str = "europe", region_rep: str = "europe", skip_fetch: bool = False) -> Dict[str, Any]:
    """Ingest matches for a single player.

    Args:
        riotid: RiotID in the form 'Name#Tagline'
        count: number of matches to fetch
        region: region code for RiotClient
        region_rep: region representation for match endpoints
        skip_fetch: if True, skip API calls and only read existing DB entries

    Returns:
        Summary dict with keys: puuid, matches_fetched, matches_saved,
        matches_skipped, matches_parse_errors, matches_fetch_errors
    """
    # Resolve DB and repositories
    db = get_db(os.getenv("MONGO_URI"))
    matches_col = db.get_collection("matches")
    repo = MatchesRepository(matches_col)

    # Prepare Riot client and limiter
    riot_key = os.getenv("RIOT_API_KEY")
    client = RiotClient(region=region)
    limiter = TokenBucketLimiter(rate=20, capacity=20)

    # Parse riotid
    if "#" not in riotid:
        raise ValueError("riotid must be in the form Name#Tagline")
    name, tagline = riotid.rsplit("#", 1)
    name = name.strip()
    tagline = tagline.strip()

    # Resolve account
    account = client.get_account_by_riot_id(name, tagline)
    puuid = account.get("puuid") or account.get("id")

    matches_fetched = 0
    matches_saved = 0
    matches_skipped = 0
    matches_parse_errors = 0
    matches_fetch_errors = 0

    if skip_fetch:
        # Count existing parsed player matches for this puuid
        try:
            pm_col = matches_col.database.get_collection("player_matches")
            existing = pm_col.count_documents({"player_puuid": puuid})
        except Exception:
            existing = 0
        return {"puuid": puuid, "matches_fetched": 0, "matches_saved": existing,
                "matches_skipped": 0, "matches_parse_errors": 0, "matches_fetch_errors": 0}

    # Fetch match ids
    match_ids = client.get_match_ids_by_puuid(puuid, count=count, region_rep=region_rep)
    matches_fetched = len(match_ids)

    for mid in match_ids:
        # Check BOTH collections before skipping — a match in `matches` but
        # not in `player_matches` still needs to be fetched and parsed.
        if repo.match_exists(mid) and repo.player_match_exists(mid, puuid):
            matches_skipped += 1
            continue

        limiter.acquire()
        try:
            m = client.get_match_by_id(mid, region_rep=region_rep)
            repo.upsert_match(m)
            # parse and upsert parsed player metrics for target puuid
            try:
                parsed = MatchParser.parse_match(m)
                participants = parsed.get("players", [])
                target = None
                for p in participants:
                    if p.get("puuid") == puuid:
                        target = p
                        break
                if target:
                    player_parsed = {
                        "player_puuid": target.get("puuid"),
                        "matchId": mid,
                        "parsed_metrics": target,
                        "championName": target.get("championName"),
                        "role": target.get("role"),
                        "timestamp": target.get("timestamp"),
                    }
                    repo.upsert_parsed_player_match(player_parsed)
                    matches_saved += 1
            except Exception as exc:
                logger.warning("Failed to parse match %s (puuid %s): %s", mid, puuid, exc)
                matches_parse_errors += 1
        except Exception as exc:
            logger.warning("Failed to fetch match %s: %s", mid, exc)
            matches_fetch_errors += 1

    return {
        "puuid": puuid,
        "matches_fetched": matches_fetched,
        "matches_saved": matches_saved,
        "matches_skipped": matches_skipped,
        "matches_parse_errors": matches_parse_errors,
        "matches_fetch_errors": matches_fetch_errors,
    }
