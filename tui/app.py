"""Heimdinger TUI — Terminal User Interface for LoL Coaching.

Entry point for the Textual application.
Launch with:
    python -m tui.app
    # or
    textual run tui/app.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path so `modules.*` imports resolve
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.keys import key_to_character as _key_to_character
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Placeholder
from textual.containers import Vertical, Horizontal

from tui.screens.dashboard import DashboardScreen
from tui.screens.player_screen import PlayerScreen
from tui.screens.coach_screen import CoachScreen
from tui.screens.pipeline_screen import PipelineScreen


class HeimdingertApp(App):
    """Main TUI application for Heimdinger LoL Coaching."""

    CSS_PATH = "heimdinger.tcss"
    TITLE = "Heimdinger — LoL Coaching"

    BINDINGS = [
        Binding("q", "quit", "Salir", priority=True),
        Binding("f1", "show_help", "Ayuda", priority=True),
        Binding("f5", "refresh", "Refrescar", priority=True),
        Binding("1", "goto_dashboard", "Dashboard", priority=True),
        Binding("2", "goto_coach", "Coach", priority=True),
        Binding("3", "goto_pipeline", "Pipeline", priority=True),
        Binding("escape", "go_back", "Volver", priority=True),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
        "coach": CoachScreen,
        "pipeline": PipelineScreen,
    }

    async def _check_bindings(self, key: str, priority: bool = False) -> bool:
        """Check bindings — includes App's own bindings, but respects focused widgets.

        Textual's built-in `_check_bindings` only iterates the screen's
        `_binding_chain`, which (a) excludes the App when a widget is focused,
        and (b) has already removed digit keys because `Input.check_consume_key`
        deletes them from every namespace in the chain.

        This override checks App-level bindings DIRECTLY — BUT only for keys
        the focused widget does NOT consume, so typing `1 2 3 4 q` in an Input
        still works.
        """
        if priority:
            # Don't intercept keys the focused widget consumes (e.g. typing
            # `1 2 3 4 q` in an Input should type characters, not navigate).
            if self.focused is not None and self.focused.check_consume_key(
                key, _key_to_character(key)
            ):
                return await super()._check_bindings(key, priority)

            app_bindings = self._bindings.key_to_bindings.get(key, ())
            for binding in app_bindings:
                if binding.priority and await self.run_action(binding.action, self):
                    return True
        return await super()._check_bindings(key, priority)

    def on_mount(self) -> None:
        self.push_screen("dashboard")

    def action_goto_dashboard(self) -> None:
        self.switch_screen("dashboard")

    def action_goto_coach(self) -> None:
        self.switch_screen("coach")

    def action_goto_pipeline(self) -> None:
        self.switch_screen("pipeline")

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_go_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_refresh(self) -> None:
        """Refresh the current screen."""
        current = self.screen
        if hasattr(current, "on_refresh"):
            current.on_refresh()  # type: ignore[union-attr]


class HelpScreen(Screen):
    """Modal help screen showing keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cerrar"),
    ]

    def compose(self) -> ComposeResult:
        from textual.widgets import Static
        from rich.text import Text
        from rich.panel import Panel

        help_text = Text()
        help_text.append("\n  ⚔  HEIMDINGER — Atajos de teclado\n\n", style="bold #C89B3C")
        help_text.append("  ─── Navegación ───\n", style="#8892A4")
        help_text.append("   1     Dashboard\n")
        help_text.append("   2     Ask the Coach\n")
        help_text.append("   3     Pipeline completo\n")
        help_text.append("\n  ─── Acciones ───\n", style="#8892A4")
        help_text.append("   F1    Esta ayuda\n")
        help_text.append("   F5    Refrescar pantalla\n")
        help_text.append("   ESC   Volver / cerrar modal\n")
        help_text.append("   Q     Salir\n")
        help_text.append("\n  ─── En formularios ───\n", style="#8892A4")
        help_text.append("   TAB   Navegar campos\n")
        help_text.append("   ↑↓    Navegar listas / tabla\n")
        help_text.append("   ENTER Seleccionar / enviar\n")

        yield Static(Panel(help_text, border_style="#C89B3C", title="Ayuda"), id="help-panel")


if __name__ == "__main__":
    HeimdingertApp().run()
