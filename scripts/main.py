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
    1. Ask the Coach — modo interactivo
    2. Pipeline completo (reportes + LLM sobre datos ya ingestados)
    3. Salir

La ingesta de datos corre automáticamente vía scripts/auto_ingest_loop.py.
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

from modules.logger import get_logger

logger = get_logger()
console = Console()


# ======================================================================
#  helpers
# ======================================================================

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
    """Correr el pipeline completo sobre datos ya ingestados."""
    console.print(Panel.fit("[bold]Pipeline completo[/bold]", border_style="blue"))

    from modules.config_manager import get_team
    from modules.data.report_builder import ReportBuilder
    from modules.db.connection import get_db
    from modules.llm.llm_advisor import LLMAdvisor

    team_path = Prompt.ask("Archivo del equipo", default="config/team.json")
    per_match = Confirm.ask("¿Reportes por partida (vs agregados)?", default=False)
    max_llm = IntPrompt.ask(
        "Máx llamadas a LLaMA por jugador (0 = deshabilitado)",
        default=0,
    )
    model = Prompt.ask("Modelo LLaMA", default="llama3.1:8b")

    try:
        team = get_team(team_path)
    except FileNotFoundError:
        console.print(f"[red]Archivo no encontrado: {team_path}[/red]")
        return

    db = get_db()
    rb = ReportBuilder()
    advisor = LLMAdvisor() if max_llm > 0 else None
    pm_col = db.get_collection("player_matches")

    for p in team:
        riotid = p.get("riotid")
        role = p.get("role")
        if not riotid:
            continue

        console.print(f"\n[bold]── {riotid} ({role}) ──[/bold]")

        # 1. Resolve puuid from already-ingested data
        name = riotid.split("#", 1)[0].strip()
        try:
            doc = pm_col.find_one({"parsed_metrics.summonerName": name}, {"player_puuid": 1})
        except Exception:
            doc = None
        puuid = doc.get("player_puuid") if doc else None
        if not puuid:
            console.print(f"  [yellow]Sin datos ingestados para {riotid}[/yellow]")
            continue
        console.print(f"  [green]✓[/green] PUUID={puuid}")

        # 2. Reports
        report = None
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
            if report.get("status") in ("empty", "error"):
                console.print(f"  [yellow]⚠ Reporte no disponible — verificar manualmente ({report.get('detail')})[/yellow]")
            else:
                console.print(
                    f"  Reporte agregado: {report.get('games_analyzed')} partidas, "
                    f"campeón más usado: {report.get('champion')}"
                )

        # 3. LLM (opcional) — reuse cached report
        if advisor and max_llm > 0:
            try:
                if report is None:
                    report = rb.build_player_report(puuid, db)
                if report.get("status") in ("empty", "error"):
                    console.print(f"  [yellow]⚠ LLM saltado — reporte no disponible[/yellow]")
                else:
                    advice = advisor.advise(report, role=role or "coach", model=model)
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
    table.add_row("1", "Ask the Coach — modo interactivo")
    table.add_row("2", "Pipeline completo (reportes + LLM)")
    table.add_row("", "")
    table.add_row("3", "[dim]Salir[/dim]")

    console.print(table)
    return IntPrompt.ask("[bold green]➤ Seleccioná una opción", default=3)


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
            _run_coach_interactive()
        elif choice == 2:
            _run_pipeline()
        elif choice == 3:
            console.print("[dim]Nos vemos![/dim]")
            break
        else:
            console.print("[red]Opción inválida[/red]")

        if choice in (1, 2):
            console.print("\n[dim]Presioná Enter para volver al menú...[/dim]", end="")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break


if __name__ == "__main__":
    main()
