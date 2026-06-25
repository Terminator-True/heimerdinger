"""Dashboard screen — overview of the team with stat cards and player table.

Matches the spec layout:
┌─────────────────────────────────────────────────────────┐
│ SIDEBAR       │  RESUMEN DEL EQUIPO     patch 14.x      │
│ ▶ Dashboard   ├──────────┬──────────┬──────────┬───────┤
│   Ingestar    │ W/L RATE │ AVG KDA  │ AVG GPM  │ VISION│
│   Coach       │   68%    │   4.2    │   487    │  38   │
│   Pipeline    ├────────────────────────────────────────┤
│ ────────────  │ EQUIPO — últimas N partidas            │
│ CONFIG        │ Nick        Rol  KDA   GPM   WR        │
│  .env  ✓      │ ───────────────────────────────────── │
│  Ollama ✓     │ TR Termi…   Top  5.1   501   70%       │
│  Riot   ✓     │ ...                                    │
│               ├────────────────────────────────────────┤
│               │ GRÁFICO: Win Rate últimas 10p          │
│               │ [plotext bar chart]                    │
└───────────────┴────────────────────────────────────────┘
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Horizontal, Vertical

from modules.riot_api.client import RiotClient
from tui.widgets.stat_card import StatCard
from tui.widgets.chart_widget import ChartWidget
from tui.utils.formatters import (
    format_kda_ratio, format_winrate, format_gpm,
    shorten_name,
)


class DashboardScreen(Screen):
    """Main dashboard showing team overview — spec-aligned."""

    BINDINGS = [
        ("f5", "refresh", "Refrescar"),
        ("escape", "go_back", "Volver"),
        ("1", "goto_dashboard", "Dashboard"),
        ("2", "goto_ingest", "Ingestar"),
        ("3", "goto_coach", "Coach"),
        ("4", "goto_pipeline", "Pipeline"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # ── Sidebar ──────────────────────────────────────
            with Vertical(id="sidebar"):
                yield Static("  ⚔  HEIMDINGER", classes="nav-title")
                yield Static("")  # spacer
                yield Static("▶ Dashboard", classes="nav-item active")
                yield Static("  Ingestar",   classes="nav-item")
                yield Static("  Coach",      classes="nav-item")
                yield Static("  Pipeline",   classes="nav-item")
                yield Static("", id="sidebar-spacer")
                yield Static(" ────────────", classes="dim")
                yield Static("  CONFIG",       classes="nav-section")
                yield Static("  .env  ⏳",     id="cfg-dotenv",  classes="nav-config")
                yield Static("  Ollama ⏳",    id="cfg-ollama",  classes="nav-config")
                yield Static("  Riot   ⏳",    id="cfg-riot",    classes="nav-config")

            # ── Main content ─────────────────────────────────
            with Vertical(id="main-content"):
                # Title row
                with Horizontal(id="content-header"):
                    yield Static("RESUMEN DEL EQUIPO", classes="content-title")
                    yield Static("patch 14.x", id="patch-version", classes="patch")
                # Stat cards row
                with Horizontal(id="stat-cards"):
                    yield StatCard("—", "W/L RATE", "#0BC4C4")
                    yield StatCard("—", "AVG KDA",  "#C89B3C")
                    yield StatCard("—", "AVG GPM",  "#C89B3C")
                    yield StatCard("—", "VISIÓN",   "#0BC4C4")
                # Table section
                yield Static("EQUIPO — últimas partidas", classes="section-label")
                yield DataTable(
                    id="team-table",
                    show_cursor=True,
                    zebra_stripes=True,
                    header_height=1,
                )
                # Chart section
                yield Static("WIN RATE — últimas partidas", classes="section-label")
                yield ChartWidget(
                    chart_type="bar",
                    title="Win Rate por Jugador",
                    color="gold",
                    id="wr-chart",
                )
        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────

    def on_mount(self) -> None:
        table = self.query_one("#team-table", DataTable)
        table.add_columns("Jugador", "Rol", "KDA", "GPM", "WR", "P")
        self._check_config_status()
        self.call_after_refresh(self._load_team_data)

    def on_screen_resume(self) -> None:
        self.call_after_refresh(self._load_team_data)

    # ── Config checks ─────────────────────────────────────

    def _check_config_status(self) -> None:
        """Check .env, Ollama, Riot availability and update sidebar."""
        from pathlib import Path

        # .env
        env_ok = Path(".env").exists()
        self._set_cfg("cfg-dotenv", "OK" if env_ok else "MISS", "#0BC4C4" if env_ok else "#E84057")

        # Ollama — quick socket check
        import socket
        ollama_ok = False
        try:
            s = socket.create_connection(("localhost", 11434), timeout=1)
            s.close()
            ollama_ok = True
        except Exception:
            pass
        self._set_cfg("cfg-ollama", "OK" if ollama_ok else "OFF", "#0BC4C4" if ollama_ok else "#E84057")

        # Riot — check env var exists
        riot_key = os.getenv("RIOT_API_KEY")
        riot_ok = bool(riot_key) and len(riot_key) > 10
        self._set_cfg("cfg-riot", "OK" if riot_ok else "NO KEY", "#0BC4C4" if riot_ok else "#E84057")

    def _set_cfg(self, widget_id: str, status: str, color: str) -> None:
        try:
            w = self.query_one(f"#{widget_id}", Static)
            name = widget_id.replace("cfg-", "").capitalize()
            w.update(f"  {name} [{color}]{status}[/]")
        except Exception:
            pass

    # ── Data loading ──────────────────────────────────────

    # ── helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_pm(pm: Dict[str, Any]) -> Dict[str, Any]:
        """Safely extract the metrics dict from a player_match document."""
        parsed = pm.get("parsed_metrics") or pm.get("metrics") or {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    async def _load_team_data(self) -> None:
        from modules.config_manager import get_team
        from modules.db.connection import get_db
        from modules.logger import get_logger

        logger = get_logger("tui.dashboard")

        try:
            team_config = get_team("config/team.json")
        except FileNotFoundError:
            logger.warning("No config/team.json found")
            self._show_empty_state()
            return

        try:
            db = get_db(os.getenv("MONGO_URI"))
        except Exception as exc:
            logger.error("DB connection failed: %s", exc)
            self._show_empty_state()
            return

        table = self.query_one("#team-table", DataTable)
        table.clear()

        total_wins = 0
        total_games = 0
        total_kda_sum = 0.0
        total_gpm_sum = 0.0
        total_vision_sum = 0.0
        player_count = 0
        rows_data: List[Dict[str, Any]] = []

        # ── Resolve riotid → puuid ──────────────────────────
        # 1) Try RiotClient API (fast parallel calls)
        # 2) Fallback: search player_matches by summonerName
        pm_col = db.get_collection("player_matches")
        resolved: List[Optional[str]] = [None] * len(team_config)
        riot_key = os.getenv("RIOT_API_KEY")

        async def _resolve_riotid(idx: int, riotid: str) -> None:
            if "#" not in riotid:
                return
            name, tag = riotid.rsplit("#", 1)
            name = name.strip()
            tag = tag.strip()
            if riot_key:
                try:
                    client = RiotClient(api_key=riot_key)
                    account = await asyncio.to_thread(
                        client.get_account_by_riot_id, name, tag
                    )
                    resolved[idx] = account.get("puuid") or account.get("id")
                    return
                except Exception:
                    pass
            # Fallback: look up summonerName in existing player_matches
            try:
                doc = pm_col.find_one(
                    {"parsed_metrics.summonerName": name},
                    {"player_puuid": 1},
                )
                if doc:
                    resolved[idx] = doc.get("player_puuid")
            except Exception:
                pass

        resolve_tasks = [
            _resolve_riotid(i, p.get("riotid", ""))
            for i, p in enumerate(team_config)
        ]
        if resolve_tasks:
            await asyncio.gather(*resolve_tasks)

        # ── Query and aggregate ─────────────────────────────
        for i, player in enumerate(team_config):
            riotid = player.get("riotid", "?")
            role = player.get("role", "?")
            puuid = resolved[i]

            player_matches: list = []
            if puuid:
                try:
                    cursor = pm_col.find(
                        {"player_puuid": puuid}
                    ).sort("_id", -1).limit(20)
                    player_matches = list(cursor)
                except Exception:
                    pass

            wins = 0
            total = len(player_matches)
            kda_acc = 0.0
            gpm_acc = 0.0
            vis_acc = 0.0

            for pm in player_matches:
                pmd = self._extract_pm(pm)
                if pmd.get("win"):
                    wins += 1
                k = pmd.get("kills", 0) or 0
                d = pmd.get("deaths", 0) or 0
                a = pmd.get("assists", 0) or 0
                kda_acc += (k + a) / max(d, 1)

                # GPM: prefer ch_goldPerMinute from rich data, else calculate
                gpm = pmd.get("ch_goldPerMinute")
                if gpm is None:
                    ge = pmd.get("goldEarned", 0) or 0
                    # crude fallback: ~30min avg game
                    gpm = ge / 30 if ge else 0
                gpm_acc += gpm

                # Vision: use visionScore
                vis_acc += pmd.get("visionScore", 0) or 0

            avg_kda = kda_acc / max(total, 1)
            avg_gpm = gpm_acc / max(total, 1)
            avg_vis = vis_acc / max(total, 1)

            rows_data.append({
                "riotid": riotid,
                "role": role,
                "wins": wins,
                "total": total,
                "avg_kda": round(avg_kda, 1),
                "avg_gpm": int(avg_gpm),
                "avg_vis": round(avg_vis, 1),
            })

            total_wins += wins
            total_games += total
            total_kda_sum += avg_kda
            total_gpm_sum += avg_gpm
            total_vision_sum += avg_vis
            player_count += 1

        # Sort by KDA descending
        rows_data.sort(key=lambda r: r["avg_kda"], reverse=True)

        for r in rows_data:
            wr = format_winrate(r["wins"], r["total"])
            name_display = shorten_name(r["riotid"], 12)
            table.add_row(name_display, r["role"], str(r["avg_kda"]),
                          str(r["avg_gpm"]), wr, str(r["total"]))

        # No data at all → empty state
        if total_games == 0:
            self._show_empty_state()
            return

        # Update stat cards
        self._update_stat_cards(
            total_wins, total_games,
            total_kda_sum / max(player_count, 1),
            total_gpm_sum / max(player_count, 1),
            total_vision_sum / max(player_count, 1),
        )

        # Win rate chart
        if rows_data:
            names = [shorten_name(r["riotid"], 6) for r in rows_data]
            rates = [(r["wins"] / max(r["total"], 1)) * 100 for r in rows_data]
            chart = self.query_one("#wr-chart", ChartWidget)
            chart.set_data(x=names, y=rates, title="Win Rate por Jugador")

    def _update_stat_cards(
        self, wins: int, total: int,
        avg_kda: float, avg_gpm: float, avg_vision: float,
    ) -> None:
        cards = self.query(StatCard)
        if len(cards) >= 4:
            cards[0].update(format_winrate(wins, total), color="#0BC4C4")
            cards[1].update(f"{avg_kda:.1f}", color="#C89B3C")
            cards[2].update(f"{avg_gpm:.0f}", color="#C89B3C")
            cards[3].update(f"{avg_vision:.1f}", color="#0BC4C4")

    def _show_empty_state(self) -> None:
        """Show 'Sin datos' in table and reset stat cards to '—'."""
        from tui.widgets.stat_card import StatCard
        table = self.query_one("#team-table", DataTable)
        table.clear()
        table.add_row("Sin datos", "—", "—", "—", "—", "—")
        for card in self.query(StatCard):
            card.update("—")

    # ── Actions ───────────────────────────────────────────

    def action_refresh(self) -> None:
        self._check_config_status()
        self.call_after_refresh(self._load_team_data)

    def action_go_back(self) -> None:
        self.app.action_go_back()

    def action_goto_dashboard(self) -> None:
        pass  # already here

    def action_goto_ingest(self) -> None:
        self.app.switch_screen("ingest")

    def action_goto_coach(self) -> None:
        self.app.switch_screen("coach")

    def action_goto_pipeline(self) -> None:
        self.app.switch_screen("pipeline")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        from tui.screens.player_screen import PlayerScreen
        try:
            row = self.query_one("#team-table", DataTable).get_row(event.row_key)
            if row and len(row) >= 2:
                player_name = str(row[0])
                role = str(row[1])
                self.app.push_screen(PlayerScreen(player_riotid=player_name, role=role))
        except Exception:
            pass
