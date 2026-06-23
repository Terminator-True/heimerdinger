# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "rich",
#     "python-dotenv",
# ]
# ///
"""Heimdinger — menú principal para herramientas de coaching de League of Legends.

Uso:
    python scripts/main.py

Opciones del menú:
    1. Ingestar un solo jugador (por Riot ID)
    2. Ingestar un equipo (desde config/team.json)
    3. Ask the Coach — modo interactivo
    4. Pipeline completo (ingest + reportes)
    5. Salir
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich import print as rprint

from modules.logger import get_logger

logger = get_logger()
console = Console()


# ======================================================================
#  helpers
# ======================================================================

def _check_riot_key() -> bool:
    """Warn and return False if RIOT_API_KEY is missing."""
    if not os.getenv("RIOT_API_KEY"):
        console.print("[yellow]⚠  RIOT_API_KEY no está configurada en .env[/yellow]")
        console.print("  Creá un archivo .env con: RIOT_API_KEY=tu_key")
        return False
    return True


def _run_ingest_one():
    """Ingestar un solo jugador por Riot ID."""
    console.print(Panel.fit("[bold]Ingestar un jugador[/bold]", border_style="cyan"))
    if not _check_riot_key():
        return

    from modules.ingest.lib import ingest_player

    riotid = Prompt.ask("[bold]Riot ID[/bold]", default="TR Terminator#1998")
    count = IntPrompt.ask("Partidas a ingestar", default=5)
    region = Prompt.ask("Región", default=os.getenv("REGION", "europe"))
    region_rep = Prompt.ask("Región (segundo parámetro)", default="europe")

    console.print(f"\nIngestando {riotid} (hasta {count} partidas)...")
    try:
        summary = ingest_player(
            riotid=riotid, count=count,
            region=region, region_rep=region_rep,
        )
        console.print(
            f"[green]✓[/green] Hecho. "
            f"PUUID: {summary.get('puuid')} "
            f"fetched={summary.get('matches_fetched')} "
            f"saved={summary.get('matches_saved')}"
        )
    except Exception as exc:
        from httpx import HTTPStatusError
        if isinstance(exc, HTTPStatusError):
            status = exc.response.status_code if exc.response is not None else None
            msg = {401: "401 Unauthorized — revisá RIOT_API_KEY en .env",
                   403: "403 Forbidden — la API key no tiene acceso",
                   404: "404 Not Found — ¿el Riot ID es correcto?",
                   429: "429 Rate limit excedido — esperá un momento"}.get(status, f"HTTP {status}")
            console.print(f"[red]{msg}[/red]")
        else:
            console.print(f"[red]Error: {exc}[/red]")


def _run_ingest_team():
    """Ingestar un equipo desde config/team.json."""
    console.print(Panel.fit("[bold]Ingestar un equipo[/bold]", border_style="cyan"))
    if not _check_riot_key():
        return

    from modules.config_manager import get_team
    from modules.ingest.lib import ingest_player
    import traceback

    team_path = Prompt.ask("Archivo del equipo", default="config/team.json")
    games = IntPrompt.ask("Partidas por jugador", default=5)
    region = Prompt.ask("Región", default=os.getenv("REGION", "europe"))

    try:
        team = get_team(team_path)
    except FileNotFoundError:
        console.print(f"[red]Archivo no encontrado: {team_path}[/red]")
        return

    console.print(f"\nIngestando {len(team)} jugadores...")
    ok = 0
    for player in team:
        riotid = player.get("riotid")
        if not riotid:
            continue
        console.print(f"  → {riotid}...", end="")
        try:
            summary = ingest_player(riotid=riotid, count=games, region=region)
            console.print(f" [green]✓[/green] ({summary.get('matches_saved')} partidas)")
            ok += 1
        except Exception as exc:
            console.print(f" [red]✗ {exc}[/red]")
            console.print(f"  [dim]{traceback.format_exc()[:200]}[/dim]")

    console.print(f"\n[green]Listo: {ok}/{len(team)} jugadores ingestados.[/green]")


def _run_coach_interactive():
    """Modo interactivo: preguntar al coach en un loop.

    La configuración se pide UNA VEZ al inicio. Después solo se muestra
    la respuesta de Ollama (sin logs, sin ruido).
    """
    console.print(Panel.fit(
        "[bold]Ask the Coach — modo interactivo[/bold]\n"
        "[dim]Escribí 'salir' para terminar. Preguntá libremente.[/dim]",
        border_style="green",
    ))

    from scripts.ask_coach import ask_coach

    model = Prompt.ask("Modelo LLaMA", default="llama3.1:8b")
    role = Prompt.ask(
        "Rol (Top/Jungle/Mid/Bot/Support, vacío = general)",
        default="",
    )
    if not role:
        role = None

    last_match = Confirm.ask("¿Solo última partida?", default=False)
    lang = Prompt.ask("Idioma", default="es")

    # Silenciar el logger para que no ensucie la salida
    import logging
    logging.getLogger("heimerdinger").setLevel(logging.WARNING)

    console.print()

    while True:
        question = input("❓ ")
        if question.lower() in ("salir", "quit", "exit", "q"):
            break

        try:
            ask_coach(
                question=question,
                role=role,
                model=model,
                last_match=last_match,
                lang=lang,
            )
        except Exception as exc:
            print(f"Error: {exc}")


def _run_pipeline():
    """Correr el pipeline completo."""
    console.print(Panel.fit("[bold]Pipeline completo[/bold]", border_style="blue"))

    from modules.config_manager import get_team
    from modules.ingest.lib import ingest_player
    from modules.data.report_builder import ReportBuilder
    from modules.db.connection import get_db
    from modules.llm.llm_advisor import LLMAdvisor

    team_path = Prompt.ask("Archivo del equipo", default="config/team.json")
    games = IntPrompt.ask("Partidas por jugador", default=5)
    region = Prompt.ask("Región", default=os.getenv("REGION", "europe"))
    per_match = Confirm.ask("¿Reportes por partida (vs agregados)?", default=False)
    max_llm = IntPrompt.ask(
        "Máx llamadas a LLaMA por jugador (0 = deshabilitado)",
        default=0,
    )
    model = Prompt.ask("Modelo LLaMA", default="llama3.1:8b")
    skip_fetch = Confirm.ask("¿Saltar fetch (usar datos ya descargados)?", default=False)

    try:
        team = get_team(team_path)
    except FileNotFoundError:
        console.print(f"[red]Archivo no encontrado: {team_path}[/red]")
        return

    db = get_db()
    rb = ReportBuilder()
    advisor = LLMAdvisor() if max_llm > 0 else None

    for p in team:
        riotid = p.get("riotid")
        role = p.get("role")
        if not riotid:
            continue

        console.print(f"\n[bold]── {riotid} ({role}) ──[/bold]")

        # 1. Ingest
        console.print("  Ingestion...", end="")
        res = ingest_player(riotid, count=games, region=region, skip_fetch=skip_fetch)
        puuid = res.get("puuid")
        if not puuid:
            console.print(f" [yellow]No se pudo resolver PUUID para {riotid}[/yellow]")
            continue
        console.print(f" [green]✓[/green] PUUID={puuid}")

        if not puuid:
            continue

        # 2. Reports
        if per_match:
            try:
                col = db.get_collection("player_matches")
                matches = list(col.find({"player_puuid": puuid}))
            except Exception:
                col = db.setdefault("player_matches", {})
                matches = [m for m in col.values() if m.get("player_puuid") == puuid]

            for mi, match in enumerate(matches, 1):
                rb.build_match_report(match, db)
                console.print(f"  [{mi}/{len(matches)}] Reporte por partida ✓")
        else:
            report = rb.build_player_report(puuid, db)
            console.print(
                f"  Reporte agregado: {report.get('games_analyzed')} partidas, "
                f"campeón más usado: {report.get('champion')}"
            )

        # 3. LLM (opcional)
        if advisor and max_llm > 0:
            try:
                report_data = rb.build_player_report(puuid, db)
                advice = advisor.advise(report_data, role=role or "coach", model=model)
                if advice:
                    console.print(f"  [green]LLM:[/green] {advice.get('summary', '')[:200]}")
            except Exception as exc:
                console.print(f"  [yellow]LLM skip: {exc}[/yellow]")

    console.print("\n[bold green]Pipeline completado.[/bold green]")


# ======================================================================
#  menu
# ======================================================================

def show_menu() -> int:
    """Mostrar menú principal y devolver la opción elegida."""
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]Heimdinger[/bold cyan]  —  League of Legends Coaching\n"
        "[dim]Ingesta • Análisis • Coaching con IA[/dim]",
        border_style="cyan",
    ))

    table = Table(show_header=False, box=None, padding=(0, 3))
    table.add_column("Opción", style="bold yellow", width=8)
    table.add_column("Acción", style="white")
    table.add_row("1", "Ingestar un solo jugador")
    table.add_row("2", "Ingestar un equipo (desde archivo)")
    table.add_row("3", "Ask the Coach — modo interactivo")
    table.add_row("4", "Pipeline completo (ingest + reportes)")
    table.add_row("", "")
    table.add_row("5", "[dim]Salir[/dim]")

    console.print(table)
    return IntPrompt.ask("[bold green]➤ Seleccioná una opción", default=5)


# ======================================================================
#  entrypoint
# ======================================================================

def main():
    while True:
        try:
            choice = show_menu()
        except (EOFError, KeyboardInterrupt):
            console.print("\n")
            break

        console.print()

        if choice == 1:
            _run_ingest_one()
        elif choice == 2:
            _run_ingest_team()
        elif choice == 3:
            _run_coach_interactive()
        elif choice == 4:
            _run_pipeline()
        elif choice == 5:
            console.print("[dim]Nos vemos![/dim]")
            break
        else:
            console.print("[red]Opción inválida[/red]")

        if choice in (1, 2, 3, 4):
            console.print("\n[dim]Presioná Enter para volver al menú...[/dim]", end="")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break


if __name__ == "__main__":
    main()
