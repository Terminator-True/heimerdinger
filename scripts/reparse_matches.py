"""Re-derive player_matches from already-stored matches — no Riot API calls.

Old ingests stored only the minimal match_parser shape in
``player_matches.parsed_metrics``, so the rich Support metrics (vision/min,
control wards, kill participation, damage/min, gold/min, wards, objectives)
never reached reports. This script re-reads the raw match docs already stored
in the ``matches`` collection, re-extracts the rich participant metrics and
merges them into the existing ``player_matches`` documents.

The merge is additive: parser-produced fields (``cs_per_min``, ``kda``, ``cs``
...) are preserved, so re-parsing can never lose data.

Usage:
  python scripts/reparse_matches.py --player <puuid>
  python scripts/reparse_matches.py --all --limit 500 --dry-run
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

from modules.data.report_builder import extract_rich_participant  # noqa: E402
from modules.db.connection import get_db  # noqa: E402
from modules.db.repositories import MatchesRepository  # noqa: E402
from modules.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

# Cap on the sample of new metric keys reported per player.
_SAMPLE_KEYS = 8


def _numeric_only(rich: dict) -> dict:
    """Keep int/float/bool values; bools are real flags (win, team_*First)."""
    return {k: v for k, v in rich.items() if isinstance(v, (int, float, bool))}


def reparse_player(db, puuid: str, limit: int = 500, dry_run: bool = False) -> dict:
    """Enrich one player's stored player_matches from the raw matches docs.

    For each stored match whose participants include *puuid*, merge the rich
    numeric metrics on top of the existing ``parsed_metrics`` (existing keys
    win) and upsert through MatchesRepository. Never raises for a single bad
    match — those are counted as errors.

    Returns a summary dict: player_puuid, scanned, enriched, skipped, errors,
    sample_new_keys.
    """
    matches_col = db.get_collection("matches")
    pm_col = db.get_collection("player_matches")
    repo = MatchesRepository(matches_col)

    scanned = enriched = skipped = errors = 0
    sample_keys = []

    for match_doc in matches_col.find({}):
        if scanned >= limit:
            break
        scanned += 1
        match_id = (match_doc.get("metadata") or {}).get("matchId")
        try:
            rich = extract_rich_participant(match_doc, puuid)
            if not rich or not match_id:
                # Participant absent (or malformed doc) — nothing to enrich.
                skipped += 1
                continue

            existing = pm_col.find_one(
                {"player_puuid": puuid, "matchId": match_id}
            ) or {}
            base = dict(existing.get("parsed_metrics") or {})
            for key, value in _numeric_only(rich).items():
                if key not in base:
                    base[key] = value
                    if key not in sample_keys and len(sample_keys) < _SAMPLE_KEYS:
                        sample_keys.append(key)

            if not dry_run:
                player_parsed = {
                    "player_puuid": puuid,
                    "matchId": match_id,
                    "parsed_metrics": base,
                    "championName": existing.get("championName") or rich.get("championName"),
                    "role": (existing.get("role")
                             or rich.get("individualPosition")
                             or rich.get("teamPosition")),
                    "timestamp": (existing.get("timestamp")
                                  or (match_doc.get("info") or {}).get("gameStartTimestamp")),
                }
                repo.upsert_parsed_player_match(player_parsed)
            enriched += 1
        except Exception as exc:
            logger.warning("Reparse failed for match %s (puuid %s): %s", match_id, puuid, exc)
            errors += 1

    return {
        "player_puuid": puuid,
        "scanned": scanned,
        "enriched": enriched,
        "skipped": skipped,
        "errors": errors,
        "sample_new_keys": sample_keys,
    }


def _all_puuids(db) -> list:
    """Every player that already has stored player_matches."""
    pm_col = db.get_collection("player_matches")
    try:
        return [p for p in pm_col.distinct("player_puuid") if p]
    except Exception:
        puuids = set()
        for doc in pm_col.find({}):
            if doc.get("player_puuid"):
                puuids.add(doc["player_puuid"])
        return sorted(puuids)


def main():
    parser = argparse.ArgumentParser(
        description="Re-derive rich player_matches metrics from stored matches "
                    "(no Riot API calls).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--player", action="append", dest="players",
                       help="Player puuid to reparse (repeatable)")
    group.add_argument("--all", action="store_true",
                       help="Reparse every player with stored player_matches")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max matches scanned per player (default 500)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing anything")
    args = parser.parse_args()

    db = get_db()
    puuids = args.players if args.players else _all_puuids(db)
    if not puuids:
        print("No players to reparse.")
        return

    totals = {"scanned": 0, "enriched": 0, "skipped": 0, "errors": 0}
    mode = "DRY-RUN" if args.dry_run else "applied"
    for puuid in puuids:
        summary = reparse_player(db, puuid, limit=args.limit, dry_run=args.dry_run)
        print(f"[{puuid}] scanned={summary['scanned']} "
              f"enriched={summary['enriched']} skipped={summary['skipped']} "
              f"errors={summary['errors']} ({mode})")
        if summary["sample_new_keys"]:
            print(f"  sample new metric keys: {', '.join(summary['sample_new_keys'])}")
        for key in totals:
            totals[key] += summary[key]

    print(f"TOTAL scanned={totals['scanned']} enriched={totals['enriched']} "
          f"skipped={totals['skipped']} errors={totals['errors']}")


if __name__ == "__main__":
    main()
