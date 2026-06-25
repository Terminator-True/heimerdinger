"""Ingest screen — form to ingest a player's matches and view progress."""

import os
from typing import Any, Dict
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Input, Button, RichLog, Static, Label, Select,
    ProgressBar,
)
from textual.containers import Horizontal, Vertical, Container
from textual import work
from textual.worker import Worker, WorkerState, WorkerFailed

from tui.utils.formatters import shorten_name


REGION_OPTIONS = [
    ("europe", "europe"),
    ("americas", "americas"),
    ("asia", "asia"),
    ("sea", "sea"),
]


class IngestScreen(Screen):
    """Form to ingest a player's matches from the Riot API."""

    BINDINGS = [
        Binding("1", "app.goto_dashboard", "Dashboard", priority=True),
        Binding("2", "app.goto_ingest", "Ingestar", priority=True),
        Binding("3", "app.goto_coach", "Coach", priority=True),
        Binding("4", "app.goto_pipeline", "Pipeline", priority=True),
        Binding("escape", "go_back", "Volver", priority=True),
        Binding("ctrl+l", "clear_log", "Limpiar log"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("INGESTAR JUGADOR", classes="gold")
            with Vertical(id="ingest-form"):
                yield Label("Riot ID")
                yield Input(placeholder="TR Terminator#1998", id="riotid")
                yield Horizontal(
                    Vertical(
                        Label("Partidas"),
                        Input(value="5", id="count", type="integer"),
                    ),
                    Vertical(
                        Label("Región"),
                        Select(
                            options=REGION_OPTIONS,
                            value="europe",
                            id="region",
                        ),
                    ),
                )
                yield Horizontal(
                    Button("▶ INGESTAR", variant="primary", id="ingest-btn"),
                    Button("✕ Cancelar", variant="default", id="cancel-btn"),
                )
            yield Static("", id="ingest-status")
            yield RichLog(id="ingest-log", highlight=True, markup=True, max_lines=1000)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ingest-btn":
            self._start_ingest()
        elif event.button.id == "cancel-btn":
            self.action_go_back()

    def _start_ingest(self) -> None:
        riotid = self.query_one("#riotid", Input).value.strip()
        count_str = self.query_one("#count", Input).value.strip()
        region = self.query_one("#region", Select).value

        if not riotid or "#" not in riotid:
            self.query_one("#ingest-log", RichLog).write(
                "[red]Error: Riot ID debe tener formato Nombre#Tagline[/red]"
            )
            return

        try:
            count = int(count_str) if count_str else 5
        except ValueError:
            count = 5

        self._run_ingest(riotid, count, str(region))

    @work(thread=True, exit_on_error=False)
    async def _run_ingest(self, riotid: str, count: int, region: str) -> None:
        """Run the ingestion in a worker thread."""
        import sys
        from pathlib import Path
        repo = str(Path(__file__).resolve().parents[2])
        if repo not in sys.path:
            sys.path.insert(0, repo)

        from modules.ingest.lib import ingest_player
        from modules.logger import get_logger
        from rich.markup import escape

        logger = get_logger("tui.ingest")

        log = self.query_one("#ingest-log", RichLog)

        def log_msg(msg: str, style: str = "") -> None:
            self.call_from_thread(log.write, f"[{style}]{escape(msg)}[/{style}]" if style else escape(msg))

        log_msg(f"▶ Iniciando ingesta para {riotid} ({count} partidas, {region})...", "bold gold")
        log_msg(f"  > Buscando PUUID...", "dim")

        try:
            result = ingest_player(riotid, count=count, region=region, region_rep=region)

            puuid = result.get("puuid", "?")
            log_msg(f"  > ✓ PUUID encontrado: {puuid}", "bold green")

            if result.get("matches_fetched", 0) > 0:
                log_msg(f"  > Partidas solicitadas: {result['matches_fetched']}", "green")
            log_msg(f"  > ✓ Guardadas: {result.get('matches_saved', 0)}", "green")
            if result.get("matches_skipped", 0) > 0:
                log_msg(f"  > ⏭ Ya existían: {result['matches_skipped']}", "dim")
            if result.get("matches_parse_errors", 0) > 0:
                log_msg(f"  > ⚠ Errores de parseo: {result['matches_parse_errors']}", "yellow")
            if result.get("matches_fetch_errors", 0) > 0:
                log_msg(f"  > ⚠ Errores de fetch: {result['matches_fetch_errors']}", "yellow")

            log_msg(f"\n✅ Ingesta completada para {riotid}", "bold #0BC4C4")

        except Exception as exc:
            log_msg(f"\n❌ Error durante la ingesta: {exc}", "bold red")
            logger.error("Ingest failed for %s: %s", riotid, exc)

    def action_clear_log(self) -> None:
        self.query_one("#ingest-log", RichLog).clear()

    def action_go_back(self) -> None:
        self.app.action_go_back()
