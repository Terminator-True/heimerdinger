"""Pipeline runner: orchestrates ingest -> parse -> compare -> report -> advise

This script wires the pieces implemented in Phase 1 and Phase 2 into a
single CLI entrypoint. It is intentionally simple: it loads a team from
config/team.json (or a supplied path), iterates players, ingests matches,
builds reports and optionally calls the LLM advisor.

Usage:
  python scripts/pipeline_runner.py --team config/team.json --games 20 --model llama3.1:8b
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure repository root is on sys.path so local `modules.*` imports resolve
load_dotenv()
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.config_manager import get_team, get_focus_player
from modules.ingest.lib import ingest_player, resolve_team_puuids
from modules.data.report_builder import ReportBuilder
from modules.data.pro_baseline import comparison_rows, load_pro_reference
from modules.llm.llm_advisor import LLMAdvisor
from modules.riot_api.client import RiotClient
from modules.db.connection import get_db
from rich.console import Console
from modules.logger import get_logger

logger = get_logger()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="config/team.json")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--region", default="europe")
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--per-match", action="store_true", help="Generate per-match reports instead of aggregated per-player reports")
    parser.add_argument("--max-llm-per-player", type=int, default=0, help="If >0, call LLM up to N times per player (0=disabled)")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--focus", action="store_true",
                        help="Ingest and report only the env-configured focus player (FOCUS_RIOTID/FOCUS_ROLE), with no team-presence gate.")
    parser.add_argument("--no-timeline", action="store_true",
                        help="In --focus mode, skip fetching match timelines (default: timelines are fetched).")
    args = parser.parse_args()

    console = Console()
    db = get_db()
    rb = ReportBuilder()

    if args.focus:
        try:
            focus = get_focus_player()
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            sys.exit(1)
        if not focus:
            console.print("[red]FOCUS_RIOTID is not set; cannot run with --focus[/red]")
            sys.exit(1)
        # Single-player mode: ingest only the focus player, no team-presence
        # gate (team_puuids=None tells ingest_player to skip the check).
        team = [focus]
        team_puuids = None
    else:
        team = get_team(args.team)
        team_puuids = resolve_team_puuids(team, RiotClient(region=args.region))

    # Timelines are only fetched on the coaching path (--focus), and can be
    # turned off explicitly to keep the Riot call count down.
    with_timeline = args.focus and not args.no_timeline

    for p in team:
        riotid = p.get("riotid")
        role = p.get("role")
        console.print(f"\n--- Processing {riotid} ({role}) ---")
        logger.info("Starting ingest for %s (%s)", riotid, role)
        res = ingest_player(riotid, count=args.games, region=args.region, skip_fetch=args.skip_fetch, team_puuids=team_puuids, with_timeline=with_timeline)
        puuid = res.get("puuid")
        if not puuid:
            console.print(f"[yellow]Could not resolve puuid for {riotid}; skipping report[/yellow]")
            logger.warning("No puuid resolved for %s", riotid)
            continue

        if args.per_match:
            # build per-match reports
            # fetch player_matches for this player
            try:
                col = db.get_collection("player_matches")
                matches = list(col.find({"player_puuid": puuid}))
            except Exception:
                matches = [m for m in db.get("player_matches", {}).values() if m.get("player_puuid") == puuid]

            console.print(f"Building {len(matches)} per-match reports for {riotid}...")
            for mi, match in enumerate(matches, 1):
                mreport = rb.build_match_report(match, db)
                console.print(f"[{mi}/{len(matches)}] Report saved: {mreport.get('player')} match={match.get('matchId')}")
        else:
            # Pro benchmark for this role (Oracle's Elixir baseline), if imported.
            pro_ref = (load_pro_reference(db, role) if role else {}) or None
            report = rb.build_player_report(puuid, db, pro_reference=pro_ref)
            console.print(f"Report for {riotid}: {report['games_analyzed']} games analyzed; champion: {report['champion']}")
            logger.info("Report built for %s: %s games", riotid, report['games_analyzed'])

            if pro_ref:
                gaps = [r for r in comparison_rows(report.get("metrics") or {}, pro_ref)
                        if r.get("pct") is not None and r["pct"] < 0][:3]
                for gap in gaps:
                    console.print(
                        f"  [yellow]vs pro[/yellow] {gap['metric']}: "
                        f"{gap['player']:.2f} vs {gap['pro']:.2f} ({gap['pct']:+.1f}%)"
                    )


if __name__ == "__main__":
    main()
