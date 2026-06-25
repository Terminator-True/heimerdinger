"""StatCard widget — compact metric display with large value and small label.

Renders as a bordered panel with the value prominent and the label below.
┌──────────┐
│   68%    │  ← value, large & colored
│ W/L RATE │  ← label, dim
└──────────┘
"""

from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from textual.widget import Widget


class StatCard(Widget):
    """A compact card showing a single metric.

    Attributes:
        value: The main value string.
        label: The label below the value.
        color: Rich CSS color for the value text.
    """

    def __init__(
        self,
        value: str = "—",
        label: str = "",
        color: str = "#C89B3C",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._value = value
        self._label = label
        self._color = color

    def render(self) -> Panel:
        value_text = Text(self._value, style=f"bold {self._color}", no_wrap=True)
        label_text = Text(f"\n{self._label}", style="#8892A4", no_wrap=True)
        content = Text.assemble(value_text, label_text)
        return Panel(
            Align.center(content, vertical="middle"),
            border_style="#2A3447",
            padding=(0, 1),
            height=5,
            subtitle="",
        )

    def update(self, value: str, label: str | None = None, color: str | None = None) -> None:
        self._value = value
        if label is not None:
            self._label = label
        if color is not None:
            self._color = color
        self.refresh()
