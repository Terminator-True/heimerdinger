"""Ingest N matches for a single player into MongoDB.

Usage:
  python scripts/ingest_one_player.py --name SummonerName --count 5 --region europe
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

# Ensure repository root is on sys.path so `modules` imports resolve when the
# script is executed from the scripts/ directory or via an IDE. Do this before
# importing any local `modules.*` packages to avoid ModuleNotFoundError.
load_dotenv()
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.logger import get_logger
logger = get_logger()

from modules.ingest.lib import ingest_player
from rich import print as rprint

console = Console()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--riotid", required=True,
                        help='RiotID in the form "Name#Tagline" (e.g. "TR Terminator#1998")')
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--region", default=os.getenv("REGION", "europe"))
    parser.add_argument("--region_rep", default="europe")
    args = parser.parse_args()

    # In normal operation we require RIOT_API_KEY; allow tests to run without it
    # by only warning rather than exiting. The underlying ingest function will
    # still operate when HTTP mocking is used in tests.
    riot_key = os.getenv("RIOT_API_KEY")
    if not riot_key:
        console.print("[yellow]Warning: RIOT_API_KEY not set in environment. Exiting for safety.[/yellow]")
        sys.exit(1)

    # Delegate to the shared ingestion implementation to avoid duplicating
    # logic between scripts.
    try:
        logger.info("Starting ingest for RiotID %s", args.riotid)
        summary = ingest_player(riotid=args.riotid, count=args.count, region=args.region, region_rep=args.region_rep)
        console.print(f"Done. PUUID: {summary.get('puuid')} fetched={summary.get('matches_fetched')} saved={summary.get('matches_saved')}")
        logger.info("Ingest completed for %s: fetched=%s saved=%s", args.riotid, summary.get('matches_fetched'), summary.get('matches_saved'))
    except Exception as exc:
        from httpx import HTTPStatusError

        if isinstance(exc, HTTPStatusError):
            status = exc.response.status_code if exc.response is not None else None
            if status == 401:
                console.print(
                    "[red]401 Unauthorized: The Riot API key was rejected by the server.[/red]"
                )
                console.print(
                    "Please verify RIOT_API_KEY in your .env or environment and ensure the key is valid and active.\n"
                    "You can test with (PowerShell):\n"
                    "$env:RIOT_API_KEY = 'your_key' ; Invoke-RestMethod -Method Get -Headers @{ 'X-Riot-Token' = $env:RIOT_API_KEY } -Uri 'https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/TR%20Terminator/1998'"
                )
                sys.exit(1)
            else:
                console.print(f"[yellow]HTTP error {status}: {exc}[/yellow]")
                logger.exception("HTTP error during ingest for %s: %s", args.riotid, exc)
                sys.exit(1)
        else:
            console.print(f"[yellow]Error resolving RiotID or ingesting matches: {exc}[/yellow]")
            logger.exception("Error resolving RiotID or ingesting matches for %s: %s", args.riotid, exc)
            sys.exit(1)


if __name__ == "__main__":
    main()
