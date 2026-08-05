"""Core ingestion helpers for players and teams.

This module centralizes the logic used by CLI scripts to ingest player
match data into the database. The existing scripts should delegate to
functions here to avoid duplication.
"""
from typing import Dict, Any, List, Optional
from modules.db.connection import get_db
from modules.db.repositories import MatchesRepository
from modules.riot_api.client import RiotClient
from modules.riot_api.rate_limiter import TokenBucketLimiter
from modules.data.match_parser import MatchParser
from modules.logger import get_logger
import os

logger = get_logger(__name__)


def resolve_team_puuids(team: List[Dict[str, Any]], client) -> List[str]:
    """Resolve each team member's riotid to a puuid, skipping failures.

    The team config stores riotids (Name#Tagline), but match participants are
    keyed by puuid, so we need the puuid per member to check presence.
    """
    puuids = []
    for player in team:
        riotid = player.get("riotid")
        if not riotid or "#" not in riotid:
            continue
        name, tagline = riotid.rsplit("#", 1)
        try:
            account = client.get_account_by_riot_id(name.strip(), tagline.strip())
            puuid = account.get("puuid") or account.get("id")
            if puuid:
                puuids.append(puuid)
        except Exception as exc:
            logger.warning("Failed to resolve riotid %s to puuid: %s", riotid, exc)
    return puuids


def ingest_player(riotid: str, count: int = 5, region: str = "europe", region_rep: str = "europe", skip_fetch: bool = False, team_puuids: Optional[List[str]] = None, min_team_members: int = 5) -> Dict[str, Any]:
    """Ingest matches for a single player.

    Args:
        riotid: RiotID in the form 'Name#Tagline'
        count: number of matches to fetch
        region: region code for RiotClient
        region_rep: region representation for match endpoints
        skip_fetch: if True, skip API calls and only read existing DB entries
        team_puuids: puuids of the full team (from team.json). When set, a
            match is only ingested if at least `min_team_members` of them are
            present among its participants; otherwise the match is discarded.
        min_team_members: minimum number of team members that must be present
            for a match to be ingested (default 5 = the whole team).

    Returns:
        Summary dict with keys: puuid, matches_fetched, matches_saved,
        matches_skipped, matches_discarded, matches_parse_errors,
        matches_fetch_errors
    """
    if team_puuids is not None and len(team_puuids) < min_team_members:
        # Fail loudly instead of silently discarding every match: a partial
        # resolution (API blip, typo in team.json) must not turn the whole
        # cycle into a silent no-op for auto_ingest_loop / scripts.
        raise RuntimeError(
            f"Only {len(team_puuids)}/{min_team_members} team puuids resolved; "
            "refusing to ingest with the team-presence filter enabled"
        )
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
    matches_discarded = 0
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
                "matches_skipped": 0, "matches_discarded": 0,
                "matches_parse_errors": 0, "matches_fetch_errors": 0}

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
            # Parse before deciding whether to save so the team-presence check
            # can run. NOTE: on parse failure the raw match is still stored
            # (same contract as before this restructure) so the dual-check
            # below short-circuits on the next run; only the player metrics
            # are skipped.
            try:
                parsed = MatchParser.parse_match(m)
                participants = parsed.get("players", [])
            except Exception as exc:
                logger.warning("Failed to parse match %s (puuid %s): %s", mid, puuid, exc)
                matches_parse_errors += 1
                repo.upsert_match(m)
                continue

            if team_puuids is not None:
                present = sum(1 for p in participants if p.get("puuid") in team_puuids)
                if present < min_team_members:
                    logger.info(
                        "Discarding match %s: only %d/%d team members present",
                        mid, present, min_team_members,
                    )
                    matches_discarded += 1
                    continue

            repo.upsert_match(m)
            target = next((p for p in participants if p.get("puuid") == puuid), None)
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
            logger.warning("Failed to fetch match %s: %s", mid, exc)
            matches_fetch_errors += 1

    return {
        "puuid": puuid,
        "matches_fetched": matches_fetched,
        "matches_saved": matches_saved,
        "matches_skipped": matches_skipped,
        "matches_discarded": matches_discarded,
        "matches_parse_errors": matches_parse_errors,
        "matches_fetch_errors": matches_fetch_errors,
    }
