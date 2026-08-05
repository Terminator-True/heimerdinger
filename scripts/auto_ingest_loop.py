"""Long-running loop that ingests the whole team every N seconds.

Reuses get_team / ingest_player / run_ingestion as-is; adds no new
infrastructure (no Celery/APScheduler/cron). Per-player failures are logged
and skipped so the cycle keeps going; SIGTERM/SIGINT trigger a clean exit.
"""
import argparse
import os
import sys
import time
import signal
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.config_manager import get_team
from modules.ingest.lib import ingest_player, resolve_team_puuids
from modules.riot_api.client import RiotClient
from modules.embeddings.ingest import run_ingestion
from modules.logger import get_logger

logger = get_logger(__name__)

_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %s, shutting down after current cycle...", signum)
    _running = False


def _sleep_in_chunks(interval, running_flag_getter):
    """Sleep `interval` seconds in 1s steps so shutdown reacts fast."""
    end = time.monotonic() + interval
    while running_flag_getter() and time.monotonic() < end:
        time.sleep(min(1, end - time.monotonic()))


def _run_cycle(args, logger):
    team = get_team(args.team)
    team_puuids = resolve_team_puuids(team, RiotClient(region=args.region))
    players_ok = 0
    players_failed = 0

    for player in team:
        riotid = player.get("riotid")
        if not riotid:
            logger.warning("Skipping player without riotid: %s", player)
            continue
        try:
            ingest_player(
                riotid=riotid,
                count=args.games,
                region=args.region,
                region_rep=args.region_rep,
                skip_fetch=args.skip_fetch,
                team_puuids=team_puuids,
            )
            players_ok += 1
        except Exception:
            players_failed += 1
            logger.error("Error ingesting %s:\n%s", riotid, traceback.format_exc())

    try:
        run_ingestion()
    except Exception:
        logger.error("run_ingestion failed:\n%s", traceback.format_exc())

    return {"players_ok": players_ok, "players_failed": players_failed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="team.json")
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--region", default=os.getenv("REGION", "europe"))
    parser.add_argument("--region_rep", default="europe")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("AUTO_INGEST_INTERVAL_SECONDS", "3600")),
    )
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("Starting auto-ingest loop (interval=%ss, team=%s)", args.interval, args.team)

    while _running:
        try:
            summary = _run_cycle(args, logger)
            logger.info(
                "Cycle done: %s ok, %s failed",
                summary["players_ok"],
                summary["players_failed"],
            )
        except Exception:
            logger.error("Unexpected error in cycle:\n%s", traceback.format_exc())

        _sleep_in_chunks(args.interval, lambda: _running)

    logger.info("Auto-ingest loop stopped.")


if __name__ == "__main__":
    main()
