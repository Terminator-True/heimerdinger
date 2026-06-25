"""Pipeline screen — orchestrate the full ingest → report → LLM pipeline."""

import os
import time
from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Static, Button, RichLog, Select, Input,
    ProgressBar, Label,
)
from textual.containers import Horizontal, Vertical
from textual import work
from textual.worker import Worker, WorkerState
from rich.markup import escape


class PipelineScreen(Screen):
    """Orchestrate the full pipeline with real-time progress per player."""

    BINDINGS = [
        Binding("1", "app.goto_dashboard", "Dashboard", priority=True),
        Binding("2", "app.goto_ingest", "Ingestar", priority=True),
        Binding("3", "app.goto_coach", "Coach", priority=True),
        Binding("4", "app.goto_pipeline", "Pipeline", priority=True),
        Binding("escape", "go_back", "Volver", priority=True),
        Binding("ctrl+l", "clear_log", "Limpiar log"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._running = False
        self._paused = False
        self._cancelled = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # Left panel: configuration
            with Vertical(id="pipeline-config", classes="content-panel"):
                yield Static("CONFIGURACIÓN", classes="gold")
                yield Label("Team file")
                yield Select(
                    options=[("config/team.json", "config/team.json")],
                    value="config/team.json",
                    id="team-select",
                )
                yield Label("Partidas por jugador")
                yield Input(value="5", id="games-count", type="integer")
                yield Label("LLM calls por jugador")
                yield Input(value="1", id="llm-count", type="integer")
                yield Label("Modelo")
                yield Select(
                    options=[
                        ("llama3.1:8b", "llama3.1:8b"),
                        ("llama3.2:3b", "llama3.2:3b"),
                        ("mistral:7b", "mistral:7b"),
                    ],
                    value="llama3.1:8b",
                    id="pipeline-model",
                )
                yield Static("")
                yield Button("▶ EJECUTAR", variant="primary", id="run-btn")
                yield Button("⏸ Pausar", variant="default", id="pause-btn", disabled=True)
                yield Button("✕ Abortar", variant="warning", id="abort-btn", disabled=True)

            # Right panel: progress and log
            with Vertical(id="pipeline-progress"):
                yield Static("PROGRESO", classes="gold")
                yield Static("", id="pipeline-status")
                yield Static("", id="player-progress")
                yield RichLog(id="pipeline-log", highlight=True, markup=True, max_lines=500)

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "run-btn":
            self._start_pipeline()
        elif btn_id == "pause-btn":
            self._toggle_pause()
        elif btn_id == "abort-btn":
            self._abort_pipeline()

    def _start_pipeline(self) -> None:
        if self._running:
            return

        team_file = self.query_one("#team-select", Select).value
        games_str = self.query_one("#games-count", Input).value.strip()
        llm_str = self.query_one("#llm-count", Input).value.strip()
        model = self.query_one("#pipeline-model", Select).value

        try:
            games = int(games_str) if games_str else 5
        except ValueError:
            games = 5
        try:
            max_llm = int(llm_str) if llm_str else 1
        except ValueError:
            max_llm = 1

        self._running = True
        self._cancelled = False
        self._paused = False

        self.query_one("#run-btn", Button).disabled = True
        self.query_one("#pause-btn", Button).disabled = False
        self.query_one("#abort-btn", Button).disabled = False

        log = self.query_one("#pipeline-log", RichLog)
        log.clear()

        self._run_pipeline(str(team_file), games, str(model), max_llm)

    @work(thread=True, exit_on_error=False)
    async def _run_pipeline(
        self, team_file: str, games: int, model: str, max_llm: int
    ) -> None:
        """Execute the full pipeline in a worker thread."""
        import sys
        from pathlib import Path
        repo = str(Path(__file__).resolve().parents[2])
        if repo not in sys.path:
            sys.path.insert(0, repo)

        from modules.config_manager import get_team
        from modules.ingest.lib import ingest_player
        from modules.data.report_builder import ReportBuilder
        from modules.llm.llm_advisor import LLMAdvisor
        from modules.db.connection import get_db
        from modules.logger import get_logger
        from rich.markup import escape

        logger = get_logger("tui.pipeline")

        def log_msg(msg: str, style: str = "") -> None:
            self.call_from_thread(
                self.query_one("#pipeline-log", RichLog).write,
                f"[{style}]{escape(msg)}[/{style}]" if style else escape(msg),
            )

        def update_status(text: str) -> None:
            self.call_from_thread(
                self.query_one("#pipeline-status", Static).update, text
            )

        def update_player_progress(text: str) -> None:
            self.call_from_thread(
                self.query_one("#player-progress", Static).update, text
            )

        try:
            team = get_team(team_file)
            db = get_db(os.getenv("MONGO_URI"))
            rb = ReportBuilder()
            advisor = LLMAdvisor(model=model)

        except Exception as exc:
            log_msg(f"❌ Error inicializando pipeline: {exc}", "bold red")
            self._finish_pipeline()
            return

        total_players = len(team)
        update_status(f"Pipeline iniciado — {total_players} jugadores, {games} partidas c/u")

        for idx, player in enumerate(team):
            if self._cancelled:
                log_msg("⛔ Pipeline abortado por el usuario.", "bold yellow")
                break

            while self._paused and not self._cancelled:
                time.sleep(0.5)

            riotid = player.get("riotid", "?")
            role = player.get("role", "?")

            update_player_progress(f"▶ Procesando {riotid} ({role}) [{idx+1}/{total_players}]")
            log_msg(f"\n── {riotid} ({role}) ──", "bold gold")

            # 1. Ingest
            log_msg("  Ingest...", "dim")
            try:
                result = ingest_player(riotid, count=games, region="europe")
                saved = result.get("matches_saved", 0)
                skipped = result.get("matches_skipped", 0)
                log_msg(f"  ✓ Ingest completado ({saved} nuevas, {skipped} existentes)", "green")
            except Exception as exc:
                log_msg(f"  ✗ Error en ingest: {exc}", "red")
                continue

            # 2. Build report
            log_msg("  Generando reporte...", "dim")
            try:
                report = rb.build_player_report(result.get("puuid", ""), db)
                log_msg("  ✓ Reporte generado", "green")
            except Exception as exc:
                log_msg(f"  ⚠ Reporte no generado: {exc}", "yellow")
                report = None

            # 3. LLM generation
            if max_llm > 0 and report:
                log_msg(f"  LLaMA generando ({max_llm} llamada(s))...", "dim")
                try:
                    for call_i in range(max_llm):
                        if self._cancelled:
                            break
                        advice = advisor.advise(report, model=model)
                        log_msg(f"  ✓ LLaMA #{call_i+1} completado", "green")
                except Exception as exc:
                    log_msg(f"  ✗ Error en LLM: {exc}", "red")
            elif max_llm > 0:
                log_msg("  ⚠ No hay reporte para LLM", "yellow")

            log_msg(f"  ✅ {riotid} completado", "bold #0BC4C4")

        # Summary
        if self._cancelled:
            update_status("⛔ Pipeline abortado")
        else:
            update_status(f"✅ Pipeline completado — {total_players} jugadores procesados")

        log_msg("\n" + "═" * 40, "dim")
        log_msg("Pipeline finalizado.", "bold #0BC4C4")

        self._finish_pipeline()

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        btn = self.query_one("#pause-btn", Button)
        btn.label = "▶ Reanudar" if self._paused else "⏸ Pausar"
        if self._paused:
            self.query_one("#pipeline-status", Static).update("⏸ Pausado")

    def _abort_pipeline(self) -> None:
        self._cancelled = True
        self._paused = False

    def _finish_pipeline(self) -> None:
        self._running = False
        self._paused = False
        self.query_one("#run-btn", Button).disabled = False
        self.query_one("#pause-btn", Button).disabled = True
        self.query_one("#abort-btn", Button).disabled = True
        self.query_one("#pause-btn", Button).label = "⏸ Pausar"

    def action_clear_log(self) -> None:
        self.query_one("#pipeline-log", RichLog).clear()

    def action_go_back(self) -> None:
        self.app.action_go_back()
