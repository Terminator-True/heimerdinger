"""CLI script to ingest a team of players from a config file."""
import argparse
import os
import sys
from pathlib import Path
import traceback
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.config_manager import get_team
from modules.ingest.lib import ingest_player, resolve_team_puuids
from modules.riot_api.client import RiotClient

console = Console()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="team.json", help="Team file under config/ or full path")
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--region", default=os.getenv("REGION", "europe"))
    parser.add_argument("--region_rep", default="europe")
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    try:
        team = get_team(args.team)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    team_puuids = resolve_team_puuids(team, RiotClient(region=args.region))

    for player in team:
        riotid = player.get("riotid")
        if not riotid:
            console.print(f"[yellow]Skipping player without riotid: {player}[/yellow]")
            continue
        console.print(f"Ingesting {riotid}...")
        try:
            summary = ingest_player(riotid=riotid, count=args.games, region=args.region, region_rep=args.region_rep, skip_fetch=args.skip_fetch, team_puuids=team_puuids)
            console.print(f"{riotid}: puuid={summary.get('puuid')} fetched={summary.get('matches_fetched')} saved={summary.get('matches_saved')} discarded={summary.get('matches_discarded')}")
        except Exception as exc:
            # Fail for this player: report the error (with traceback) and continue with next
            console.print(f"[red]Error ingesting {riotid}: {exc}[/red]")
            console.print(f"[red]{traceback.format_exc()}[/red]")
            console.print("[yellow]Continuing with next player...[/yellow]")
            continue


if __name__ == "__main__":
    main()
