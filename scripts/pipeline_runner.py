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

from modules.config_manager import get_team
from modules.ingest.lib import ingest_player
from modules.data.report_builder import ReportBuilder
from modules.llm.llm_advisor import LLMAdvisor
from modules.db.connection import get_db
from rich.console import Console
from modules.logger import get_logger

logger = get_logger()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="config/team.json")
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--region", default="europe")
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    console = Console()
    team = get_team(args.team)
    db = get_db()
    rb = ReportBuilder()
    advisor = LLMAdvisor()

    for p in team:
        riotid = p.get("riotid")
        role = p.get("role")
        console.print(f"\n--- Processing {riotid} ({role}) ---")
        logger.info("Starting ingest for %s (%s)", riotid, role)
        res = ingest_player(riotid, count=args.games, region=args.region, skip_fetch=args.skip_fetch)
        puuid = res.get("puuid")
        if not puuid:
            console.print(f"[yellow]Could not resolve puuid for {riotid}; skipping report[/yellow]")
            logger.warning("No puuid resolved for %s", riotid)
            continue

        report = rb.build_player_report(puuid, db)
        console.print(f"Report for {riotid}: {report['games_analyzed']} games analyzed; champion: {report['champion']}")
        logger.info("Report built for %s: %s games", riotid, report['games_analyzed'])

        # Ask LLM for advice (best-effort)
        try:
            advice = advisor.advise(report, model=args.model)
            console.print("LLM advice summary:\n", advice.get("raw_advice_text", "(no advice)"))
        except Exception as e:
            console.print(f"[red]LLM advice failed: {e}[/red]")


if __name__ == "__main__":
    main()
