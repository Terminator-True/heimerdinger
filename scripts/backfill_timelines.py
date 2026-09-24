"""Backfill compacted match timelines for already-stored matches.

Unlike ``reparse_matches.py`` this one DOES call Riot: timelines are not
derivable offline, so every match missing a stored timeline is fetched from
match-v5 and stored compacted in the ``timelines`` collection.

Usage:
  python scripts/backfill_timelines.py --player <puuid>
  python scripts/backfill_timelines.py --all --limit 500 --dry-run
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure repository root is on sys.path so local `modules.*` imports resolve.
load_dotenv()
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.data.timeline import compact_timeline  # noqa: E402
from modules.db.connection import get_db  # noqa: E402
from modules.db.repositories import MatchesRepository  # noqa: E402
from modules.logger import get_logger  # noqa: E402
from modules.riot_api.client import RiotClient  # noqa: E402
from modules.riot_api.rate_limiter import TokenBucketLimiter  # noqa: E402

logger = get_logger(__name__)


def _player_match_ids(db, puuid: str, limit: int) -> list:
    """Ordered, de-duplicated matchIds from the player's player_matches."""
    pm_col = db.get_collection("player_matches")
    ids = []
    seen = set()
    for doc in pm_col.find({"player_puuid": puuid}):
        mid = doc.get("matchId")
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)
        if len(ids) >= limit:
            break
    return ids


def _all_match_ids(db, limit: int) -> list:
    """Ordered matchIds from every stored match."""
    matches_col = db.get_collection("matches")
    ids = []
    for doc in matches_col.find({}):
        mid = (doc.get("metadata") or {}).get("matchId")
        if mid:
            ids.append(mid)
        if len(ids) >= limit:
            break
    return ids


def backfill_player(db, puuid, client, limit: int = 500, dry_run: bool = False,
                    region_rep: str = "europe", limiter=None) -> dict:
    """Fetch and store compacted timelines for matches missing one.

    With *puuid* set it scans that player's stored ``player_matches``; with
    None it scans every stored match. Never raises for a single bad match —
    those are counted as errors.

    Returns a summary dict: player_puuid, scanned, fetched, stored, skipped,
    errors. ``stored`` stays 0 in dry-run mode.
    """
    matches_col = db.get_collection("matches")
    repo = MatchesRepository(matches_col)
    limiter = limiter or TokenBucketLimiter(rate=20, capacity=20)

    match_ids = (_player_match_ids(db, puuid, limit) if puuid
                 else _all_match_ids(db, limit))

    scanned = fetched = stored = skipped = errors = 0
    for mid in match_ids:
        scanned += 1
        if repo.timeline_exists(mid):
            skipped += 1
            continue

        fetched += 1
        if dry_run:
            continue

        try:
            limiter.acquire()
            timeline_doc = client.get_match_timeline(mid, region_rep=region_rep)
            repo.upsert_timeline(mid, compact_timeline(timeline_doc))
            stored += 1
        except Exception as exc:
            logger.warning("Timeline backfill failed for match %s: %s", mid, exc)
            errors += 1

    return {
        "player_puuid": puuid,
        "scanned": scanned,
        "fetched": fetched,
        "stored": stored,
        "skipped": skipped,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill compacted match timelines for stored matches "
                    "(calls the Riot API).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--player", action="append", dest="players",
                       help="Player puuid to backfill (repeatable)")
    group.add_argument("--all", action="store_true",
                       help="Backfill every stored match")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max matches scanned per player (default 500)")
    parser.add_argument("--region", default="europe",
                        help="Regional route host for match-v5 (default europe)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be fetched without writing anything")
    args = parser.parse_args()

    db = get_db()
    client = RiotClient(region=args.region)
    limiter = TokenBucketLimiter(rate=20, capacity=20)

    puuids = args.players if args.players else [None]
    totals = {"scanned": 0, "fetched": 0, "stored": 0, "skipped": 0, "errors": 0}
    mode = "DRY-RUN" if args.dry_run else "applied"
    for puuid in puuids:
        summary = backfill_player(db, puuid, client, limit=args.limit,
                                  dry_run=args.dry_run, region_rep=args.region,
                                  limiter=limiter)
        label = puuid or "[all]"
        print(f"[{label}] scanned={summary['scanned']} fetched={summary['fetched']} "
              f"stored={summary['stored']} skipped={summary['skipped']} "
              f"errors={summary['errors']} ({mode})")
        for key in totals:
            totals[key] += summary[key]

    print(f"TOTAL scanned={totals['scanned']} fetched={totals['fetched']} "
          f"stored={totals['stored']} skipped={totals['skipped']} "
          f"errors={totals['errors']}")


if __name__ == "__main__":
    main()
