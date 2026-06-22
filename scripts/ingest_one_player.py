"""Ingest N matches for a single player into MongoDB.

Usage:
  python scripts/ingest_one_player.py --name SummonerName --count 5 --region EUW1
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
# Ensure repository root is on sys.path so `modules` imports resolve when the
# script is executed from the scripts/ directory or via an IDE.
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.riot_api.client import RiotClient
from modules.riot_api.rate_limiter import TokenBucketLimiter
from modules.db.connection import get_db
from modules.db.repositories import MatchesRepository
from modules.data.match_parser import MatchParser
from rich import print as rprint

console = Console()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--riotid", required=True,
                        help='RiotID in the form "Name#Tagline" (e.g. "TR Terminator#1998")')
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--region", default=os.getenv("REGION", "EUW"))
    parser.add_argument("--region_rep", default="europe")
    args = parser.parse_args()

    # In normal operation we require RIOT_API_KEY; allow tests to run without it
    # by only warning rather than exiting. The RiotClient will still work when
    # HTTP mocking is used in tests.
    riot_key = os.getenv("RIOT_API_KEY")
    if not riot_key:
        console.print("[yellow]Warning: RIOT_API_KEY not set in environment. Exiting for safety.[/yellow]")
        sys.exit(1)

    db = get_db(os.getenv("MONGO_URI"))
    matches_col = db.get_collection("matches")
    repo = MatchesRepository(matches_col)

    client = RiotClient(region=args.region)
    limiter = TokenBucketLimiter(rate=20, capacity=20)

    # RiotID parsing: expect Name#Tagline or Name#1998; strip whitespace
    if "#" not in args.riotid:
        console.print("[red]riotid must be in the form Name#Tagline[/red]")
        sys.exit(1)
    name, tagline = args.riotid.rsplit("#", 1)
    name = name.strip()
    tagline = tagline.strip()

    console.print(f"Resolving RiotID '{name}#{tagline}'...")
    try:
        account = client.get_account_by_riot_id(name, tagline)
    except Exception as exc:
        # Prefer httpx HTTPStatusError details when available
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
                    "$env:RIOT_API_KEY = 'your_key' ; Invoke-RestMethod -Method Get -Headers @{ 'X-Riot-Token' = $env:RIOT_API_KEY } -Uri 'https://euw1.api.riotgames.com/riot/account/v1/accounts/by-riot-id/TR%20Terminator/1998'"
                )
                sys.exit(1)
            else:
                console.print(f"[yellow]HTTP error {status}: {exc}[/yellow]")
                sys.exit(1)
        else:
            console.print(f"[yellow]Error resolving RiotID: {exc}[/yellow]")
            sys.exit(1)

    # account response may contain puuid depending on region; adapt accordingly
    puuid = account.get("puuid") or account.get("id")
    console.print(f"PUUID: {puuid}")

    console.print(f"Fetching last {args.count} match IDs...")
    match_ids = client.get_match_ids_by_puuid(puuid, count=args.count, region_rep=args.region_rep)
    console.print(f"Found {len(match_ids)} matches")

    saved = 0
    for mid in match_ids:
        limiter.acquire()
        try:
            m = client.get_match_by_id(mid, region_rep=args.region_rep)
            repo.upsert_match(m)
            # Parse match and persist player-specific parsed metrics for the target puuid
            try:
                parsed = MatchParser.parse_match(m)
                # find participant matching puuid
                participants = parsed.get("players", [])
                target = None
                for p in participants:
                    if p.get("puuid") == puuid:
                        target = p
                        break
                if not target:
                    console.print(f"[yellow]Warning: parsed participant for puuid {puuid} not found in match {mid}[/yellow]")
                else:
                    player_parsed = {
                        "player_puuid": target.get("puuid"),
                        "matchId": mid,
                        "parsed_metrics": target,
                        "championName": target.get("championName"),
                        "role": target.get("role"),
                        "timestamp": target.get("timestamp"),
                    }
                    repo.upsert_parsed_player_match(player_parsed)
            except Exception as e:
                console.print(f"[yellow]Warning: failed to parse/persist parsed player metrics for match {mid}: {e}[/yellow]")
            saved += 1
            console.print(f"Saved match {mid}")
        except Exception as e:
            console.print(f"[yellow]Error fetching/saving match {mid}: {e}[/yellow]")

    console.print(f"Done. Saved {saved} matches.")


if __name__ == "__main__":
    main()
