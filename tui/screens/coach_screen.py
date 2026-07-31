"""Coach screen — interactive chat with the LLM coach via Ollama streaming."""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Input, Button, RichLog, Static, Label, Select,
)
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import work
from rich.markup import escape

from tui.utils.formatters import shorten_name


class CoachScreen(Screen):
    """Interactive chat with the AI coach using streaming Ollama responses."""

    BINDINGS = [
        Binding("1", "app.goto_dashboard", "Dashboard", priority=True),
        Binding("2", "app.goto_coach", "Coach", priority=True),
        Binding("3", "app.goto_pipeline", "Pipeline", priority=True),
        Binding("escape", "go_back", "Volver", priority=True),
        Binding("ctrl+l", "clear_chat", "Limpiar chat"),
        Binding("ctrl+p", "change_player", "Cambiar jugador"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._model = "llama3.1:8b"
        self._player = "TR Terminator#1998"
        self._role = "Support"
        self._messages: List[Dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("🤖 ASK THE COACH", classes="gold")
            yield Label(
                f"Modelo: {self._model}   Jugador: {self._player}   Rol: {self._role}",
                id="coach-header-info",
                classes="dim",
            )

            # Chat area
            with ScrollableContainer(id="chat-area"):
                yield RichLog(id="chat-log", highlight=True, markup=True, max_lines=2000)

            # Input area
            with Horizontal(id="chat-input-area"):
                yield Input(
                    placeholder="Pregunta al coach...",
                    id="question-input",
                )
                yield Button("▶ Enviar", variant="primary", id="send-btn")

            with Horizontal(id="chat-config"):
                yield Select(
                    options=[
                        ("llama3.1:8b", "llama3.1:8b"),
                        ("llama3.2:3b", "llama3.2:3b"),
                        ("mistral:7b", "mistral:7b"),
                    ],
                    value=self._model,
                    id="model-select",
                    prompt="Modelo",
                )
                yield Button("⚙ Config", variant="default", id="config-btn")

        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one("#chat-log", RichLog)
        chat.write("[bold #C89B3C]🤖 ¡Bienvenido a Ask the Coach![/bold #C89B3C]")
        chat.write("[dim]Haz una pregunta sobre tu rendimiento en League of Legends.[/dim]")
        chat.write("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "question-input" and event.value.strip():
            self._send_question(event.value.strip())
            event.input.value = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            inp = self.query_one("#question-input", Input)
            if inp.value.strip():
                self._send_question(inp.value.strip())
                inp.value = ""
        elif event.button.id == "config-btn":
            self._show_config_popup()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "model-select":
            self._model = str(event.value)

    def _send_question(self, question: str) -> None:
        chat = self.query_one("#chat-log", RichLog)
        chat.write(f"[bold #0BC4C4]👤 Tú:[/bold #0BC4C4] {escape(question)}")
        self._messages.append({"role": "user", "content": question})
        self._stream_response(question)

    @work(thread=True, exit_on_error=False)
    async def _stream_response(self, question: str) -> None:
        """Classify question, retrieve context, build prompt, and stream answer."""
        import sys
        repo = str(Path(__file__).resolve().parents[2])
        if repo not in sys.path:
            sys.path.insert(0, repo)

        import httpx
        from modules.llm.retrieval import retrieve_for_category
        from modules.llm.question_classifier import classify_question
        from modules.llm.prompt_engineer import PromptEngineer
        from modules.db.connection import get_db
        from modules.logger import get_logger
        from modules.data.report_builder import ReportBuilder, get_full_match, extract_rich_participant
        from rich.markup import escape

        logger = get_logger("tui.coach")
        chat = self.query_one("#chat-log", RichLog)

        try:
            # 1. classify the question
            classification = classify_question(question)
            category_id = classification.get("category_id", "general")
            logger.info("Question classified: %s (confidence=%.2f)", category_id, classification.get("confidence", 0))

            # 2. retrieve context from DB
            db = get_db(os.getenv("MONGO_URI"))
            rb = ReportBuilder()
            passages = retrieve_for_category(
                category_id=category_id,
                role=self._role,
                db=db,
                limit=5,
            )

            # 3. get a recent aggregation report for structured stats
            report = None
            try:
                # Resolve puuid and build a report
                from modules.ingest.lib import ingest_player
                from modules.data.report_builder import ReportBuilder
                # Try to find the player in player_matches to get puuid
                pm_col = db.get_collection("player_matches")
                pm_sample = pm_col.find_one({})
                if pm_sample and pm_sample.get("player_puuid"):
                    puuid = pm_sample["player_puuid"]
                    report = rb.build_player_report(puuid, db)
            except Exception:
                pass

            if not report or not isinstance(report, dict) or "metrics" not in report:
                report = {"player": self._player, "role": self._role, "metrics": {}}

            # 4. build the prompt
            pe = PromptEngineer()
            prompt = pe.build_prompt(
                player_report=report,
                role=self._role,
                passages=passages,
                language="es",
            )

            # 5. stream response from Ollama
            self.call_from_thread(chat.write, f"[bold #C89B3C]🤖 Coach:[/bold #C89B3C]")

            accumulated = ""
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {"temperature": 0.7},
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                accumulated += token
                        except json.JSONDecodeError:
                            continue

            # Write the complete response
            self.call_from_thread(chat.write, escape(accumulated.strip()))
            self.call_from_thread(chat.write, "")
            self._messages.append({"role": "assistant", "content": accumulated.strip()})

            # 6. save artifact
            artifacts_dir = Path(repo) / "reports" / "ollama_responses"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            artifact = {
                "timestamp": datetime.now().isoformat(),
                "player": self._player,
                "role": self._role,
                "question": question,
                "response": accumulated.strip(),
                "model": self._model,
                "category": category_id,
                "passages_count": len(passages),
            }
            with open(
                artifacts_dir / f"coach_tui_{datetime.now():%Y%m%d_%H%M%S}.json",
                "w", encoding="utf-8",
            ) as f:
                json.dump(artifact, f, indent=2, ensure_ascii=False)

        except Exception as exc:
            logger.error("Coach response failed: %s", exc)
            self.call_from_thread(
                chat.write,
                f"[red]❌ Error: {escape(str(exc))}[/red]\n"
                "[dim]Asegúrate de que Ollama esté corriendo en localhost:11434[/dim]",
            )
            self.call_from_thread(chat.write, "")

    def _show_config_popup(self) -> None:
        """Show a modal to change player/role configuration."""
        from textual.screen import Screen as ModalScreen

        class ConfigModal(ModalScreen):
            def compose(self):
                from textual.widgets import Input, Button, Label
                from textual.containers import Vertical, Horizontal
                with Vertical():
                    yield Label("Configuración del Coach", classes="gold")
                    yield Label("Riot ID del jugador")
                    yield Input(placeholder="TR Terminator#1998", id="cfg-riotid")
                    yield Label("Rol")
                    yield Input(placeholder="Support", id="cfg-role")
                    with Horizontal():
                        yield Button("Guardar", variant="primary", id="cfg-save")
                        yield Button("Cancelar", variant="default", id="cfg-cancel")

            def on_button_pressed(self, event):
                if event.button.id == "cfg-save":
                    riotid = self.query_one("#cfg-riotid", Input).value.strip()
                    role = self.query_one("#cfg-role", Input).value.strip()
                    parent = self.app.screen
                    if isinstance(parent, CoachScreen):
                        if riotid:
                            parent._player = riotid
                        if role:
                            parent._role = role
                        parent._update_header()
                    self.app.pop_screen()
                elif event.button.id == "cfg-cancel":
                    self.app.pop_screen()

        self.app.push_screen(ConfigModal())

    def _update_header(self) -> None:
        label = self.query_one("#coach-header-info", Label)
        if label:
            label.update(
                f"Modelo: {self._model}   Jugador: {self._player}   Rol: {self._role}"
            )

    def action_clear_chat(self) -> None:
        self.query_one("#chat-log", RichLog).clear()
        self._messages.clear()

    def action_change_player(self) -> None:
        self._show_config_popup()

    def action_go_back(self) -> None:
        self.app.action_go_back()
