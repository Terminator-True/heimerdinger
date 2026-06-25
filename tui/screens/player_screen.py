"""Player detail screen — per-player stats, match history, and charts."""

import os
from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, Label, RichLog, Button
from textual.containers import Horizontal, Vertical
from textual import work

from tui.widgets.stat_card import StatCard
from tui.widgets.chart_widget import ChartWidget
from tui.utils.formatters import (
    format_kda, format_gpm, format_duration,
    format_kda_ratio, shorten_name,
)
from tui.utils.benchmarks import compare_to_benchmark


class PlayerScreen(Screen):
    """Detail view for a single player with metrics and charts."""

    BINDINGS = [
        Binding("1", "app.goto_dashboard", "Dashboard", priority=True),
        Binding("2", "app.goto_ingest", "Ingestar", priority=True),
        Binding("3", "app.goto_coach", "Coach", priority=True),
        Binding("4", "app.goto_pipeline", "Pipeline", priority=True),
        Binding("escape", "go_back", "Volver", priority=True),
        Binding("f5", "refresh", "Refrescar"),
    ]

    def __init__(self, player_riotid: str = "", role: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._player_riotid = player_riotid
        self._role = role
        self._player_matches: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # Left column: match history
            with Vertical(id="player-left"):
                yield Static(f"  {self._player_riotid}  •  {self._role}", classes="gold")
                yield Static("ÚLTIMAS PARTIDAS", classes="label")
                yield DataTable(id="match-history", show_cursor=True, zebra_styles=True)
                yield Static("TENDENCIA KDA", classes="label")
                yield ChartWidget(chart_type="line", title="KDA por partida", color="teal", id="kda-trend")

            # Right column: aggregated metrics + charts
            with Vertical(id="player-right"):
                yield Static("MÉTRICAS AGREGADAS", classes="label")
                with Horizontal():
                    yield StatCard("—", "KDA MEDIO", "#0BC4C4")
                    yield StatCard("—", "GPM MEDIO", "#C89B3C")
                    yield StatCard("—", "CS@10", "#C89B3C")
                    yield StatCard("—", "VISIÓN/MIN", "#0BC4C4")
                yield Static("GPM por partida", classes="label")
                yield ChartWidget(chart_type="line", title="GPM", color="gold", id="gpm-chart")

        # IA feedback section
        with Horizontal(id="player-feedback"):
            yield Static("FEEDBACK IA  ", classes="label")
            yield Button("Generar con LLaMA ▶", variant="primary", id="gen-feedback-btn")
            yield RichLog(id="ai-feedback", highlight=True, markup=True, max_lines=20)

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#match-history", DataTable)
        table.add_columns("Resultado", "Campeón", "KDA", "GPM", "CS@10", "Duración")
        self.call_after_refresh(self._load_player_data)

    def on_screen_resume(self) -> None:
        self.call_after_refresh(self._load_player_data)

    async def _load_player_data(self) -> None:
        """Fetch player matches from DB and update all widgets."""
        from modules.db.connection import get_db
        from modules.logger import get_logger

        logger = get_logger("tui.player")

        try:
            db = get_db(os.getenv("MONGO_URI"))
        except Exception as exc:
            logger.error("DB connection failed: %s", exc)
            return

        try:
            pm_col = db.get_collection("player_matches")
            cursor = pm_col.find({}).sort("_id", -1).limit(20)
            self._player_matches = list(cursor)
        except Exception as exc:
            logger.error("Failed to query player_matches: %s", exc)
            self._player_matches = []

        if not self._player_matches:
            self._show_empty_state("No se encontraron partidas para este jugador.")
            return

        # Update match history table
        self._update_match_table()

        # Aggregate metrics
        total_kda = 0.0
        total_gpm = 0.0
        total_cs10 = 0.0
        total_vision = 0.0
        match_count = len(self._player_matches)

        kda_values = []
        gpm_values = []
        match_labels = []

        for i, pm in enumerate(self._player_matches):
            metrics = pm.get("parsed_metrics") or {}
            kills = metrics.get("kills", 0)
            deaths = metrics.get("deaths", 0)
            assists = metrics.get("assists", 0)
            kda_val = format_kda_ratio(kills, deaths, assists)
            total_kda += kda_val
            kda_values.append(kda_val)

            gpm_val = metrics.get("challenges", {}).get("goldPerMinute", 0)
            total_gpm += gpm_val
            gpm_values.append(gpm_val)

            cs10 = metrics.get("challenges", {}).get("laneMinionsFirst10Minutes", 0)
            total_cs10 += cs10

            vision = metrics.get("challenges", {}).get("visionScorePerMinute", 0)
            total_vision += vision

            match_labels.append(f"#{match_count - i}")

        avg_kda = total_kda / max(match_count, 1)
        avg_gpm = total_gpm / max(match_count, 1)
        avg_cs10 = total_cs10 / max(match_count, 1)
        avg_vision = total_vision / max(match_count, 1)

        # Update stat cards
        cards = self.query(StatCard)
        if len(cards) >= 4:
            cards[0].update(f"{avg_kda:.1f}", "KDA MEDIO", "#0BC4C4")
            cards[1].update(f"{avg_gpm:.0f}", "GPM MEDIO", "#C89B3C")
            cs_bench = compare_to_benchmark(self._role, "cs_per_min", avg_cs10)
            cs_color = "#0BC4C4" if cs_bench["is_above"] else "#E84057"
            cards[2].update(f"{avg_cs10:.0f}", "CS@10", cs_color)
            vis_bench = compare_to_benchmark(self._role, "vision_per_min", avg_vision)
            vis_color = "#0BC4C4" if vis_bench["is_above"] else "#E84057"
            cards[3].update(f"{avg_vision:.1f}", "VISIÓN/MIN", vis_color)

        # KDA trend chart
        kda_chart = self.query_one("#kda-trend", ChartWidget)
        kda_chart.set_data(x=match_labels, y=kda_values, title="KDA por partida")

        # GPM chart
        gpm_chart = self.query_one("#gpm-chart", ChartWidget)
        gpm_chart.set_data(x=match_labels, y=gpm_values, title="GPM por partida")

    def _update_match_table(self) -> None:
        table = self.query_one("#match-history", DataTable)
        table.clear()

        for pm in self._player_matches[:10]:
            metrics = pm.get("parsed_metrics") or {}
            win = metrics.get("win", False)
            champion = metrics.get("championName", "?")
            kills = metrics.get("kills", 0)
            deaths = metrics.get("deaths", 0)
            assists = metrics.get("assists", 0)
            gpm = metrics.get("challenges", {}).get("goldPerMinute", 0)
            cs10 = metrics.get("challenges", {}).get("laneMinionsFirst10Minutes", 0)
            duration = metrics.get("gameDuration", 0)

            result = "✓" if win else "✗"
            result_style = "win" if win else "loss"

            table.add_row(
                f"[{result_style}]{result}[/{result_style}]",
                champion,
                format_kda(kills, deaths, assists),
                format_gpm(gpm),
                f"{cs10:.0f}",
                format_duration(int(duration)),
        )

    def _show_empty_state(self, message: str) -> None:
        table = self.query_one("#match-history", DataTable)
        table.clear()
        table.add_row("—", "—", "—", "—", "—", "—")

    def action_refresh(self) -> None:
        self.call_after_refresh(self._load_player_data)

    def action_go_back(self) -> None:
        self.app.action_go_back()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gen-feedback-btn":
            self._generate_feedback()

    def _generate_feedback(self) -> None:
        """Generate AI feedback for this player using Ollama."""
        feedback = self.query_one("#ai-feedback", RichLog)
        feedback.clear()
        feedback.write("[dim]Generando feedback con LLaMA...[/dim]")

        self.call_after_refresh(self._do_generate_feedback)

    @work(thread=True)
    async def _do_generate_feedback(self) -> None:
        """Run LLM feedback generation in a worker thread."""
        import sys
        from pathlib import Path
        repo = str(Path(__file__).resolve().parents[2])
        if repo not in sys.path:
            sys.path.insert(0, repo)

        from modules.llm.ollama_client import OllamaClient
        from modules.llm.prompt_engineer import PromptEngineer
        from modules.logger import get_logger
        from rich.markup import escape

        logger = get_logger("tui.player")
        feedback = self.query_one("#ai-feedback", RichLog)

        try:
            prompt_builder = PromptEngineer()
            client = OllamaClient()

            # Build a minimal stats summary
            if self._player_matches:
                recent = self._player_matches[0]
                metrics = recent.get("parsed_metrics") or {}
                stats_summary = (
                    f"Campeón: {metrics.get('championName', '?')}, "
                    f"KDA: {metrics.get('kills', 0)}/{metrics.get('deaths', 0)}/{metrics.get('assists', 0)}, "
                    f"Rol: {self._role}"
                )
            else:
                stats_summary = f"Jugador: {self._player_riotid}, Rol: {self._role}"

            prompt = prompt_builder.build_prompt(
                question=f"Dame consejos de coaching para {self._player_riotid} ({self._role})",
                stats_context=stats_summary,
            )
            result = client.generate(prompt)
            response_text = result.get("response", "")

            self.call_from_thread(feedback.clear)
            self.call_from_thread(feedback.write, f"[bold #C89B3C]🤖 Feedback para {self._player_riotid}:[/bold #C89B3C]\n")
            for line in response_text.strip().split("\n"):
                self.call_from_thread(feedback.write, escape(line))

        except Exception as exc:
            logger.error("LLM feedback failed: %s", exc)
            self.call_from_thread(feedback.clear)
            self.call_from_thread(
                feedback.write,
                f"[red]Error generando feedback: {escape(str(exc))}[/red]\n"
                "[dim]Asegúrate de que Ollama esté corriendo en localhost:11434[/dim]"
            )
