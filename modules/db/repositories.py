from pymongo.collection import Collection
from datetime import datetime
from typing import Dict, Any


class MatchesRepository:
    def __init__(self, collection: Collection):
        self.col = collection
        # ensure unique index on metadata.matchId if available
        try:
            self.col.create_index([("metadata.matchId", 1)], unique=True)
        except Exception:
            pass

    def match_exists(self, match_id: str) -> bool:
        """Return True if a document with the given metadata.matchId exists."""
        return self.col.count_documents({"metadata.matchId": match_id}, limit=1) > 0

    def upsert_match(self, match_json: dict, skip_if_exists: bool = False) -> bool:
        """Insert or update a match document.

        Args:
            match_json: the full match JSON from Riot API
            skip_if_exists: if True, skip the upsert when the match already exists

        Returns:
            True if the match was inserted/updated, False if it was skipped.
        """
        match_id = match_json.get("metadata", {}).get("matchId")
        if not match_id:
            # try legacy key
            match_id = match_json.get("gameId")
        if not match_id:
            raise ValueError("match JSON missing match id")

        if skip_if_exists and self.match_exists(match_id):
            return False

        self.col.update_one({"metadata.matchId": match_id}, {"$set": match_json}, upsert=True)
        return True

    def upsert_parsed_player_match(self, player_parsed: Dict[str, Any]):
        """Upsert the parsed player metrics into a separate collection.

        The document is keyed uniquely by (player_puuid, matchId).
        Expected keys in player_parsed: player_puuid, matchId, parsed_metrics,
        championName, role, timestamp (timestamp optional).
        """
        # Validate required fields
        player_puuid = player_parsed.get("player_puuid") or player_parsed.get("puuid")
        match_id = player_parsed.get("matchId")
        if not player_puuid or not match_id:
            raise ValueError("player_parsed must include player_puuid and matchId")

        db = None
        try:
            db = self.col.database
        except Exception:
            # Fallback: if collection doesn't expose database, raise
            raise RuntimeError("Unable to access database from collection")

        pm_col = db.get_collection("player_matches")

        # Ensure unique index on (player_puuid, matchId)
        try:
            pm_col.create_index([("player_puuid", 1), ("matchId", 1)], unique=True)
        except Exception:
            # best-effort index creation; ignore to remain idempotent
            pass

        doc = {
            "player_puuid": player_puuid,
            "matchId": match_id,
            "parsed_metrics": player_parsed.get("parsed_metrics") or player_parsed.get("metrics") or {},
            "championName": player_parsed.get("championName"),
            "role": player_parsed.get("role"),
            "timestamp": player_parsed.get("timestamp"),
        }

        # Use upsert to keep idempotency
        filter_q = {"player_puuid": player_puuid, "matchId": match_id}
        update_q = {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}}
        pm_col.update_one(filter_q, update_q, upsert=True)
