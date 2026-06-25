"""ChartWidget — wraps plotext ASCII charts inside a Textual Widget."""

from typing import Optional

import plotext as plt
from rich.text import Text
from textual.widget import Widget


class ChartWidget(Widget):
    """Render plotext charts as inline ASCII inside Textual.

    Usage:
        chart = ChartWidget(chart_type="bar")
        chart.set_data(categories=["Top", "Jgl"], values=[68, 55])
    """

    def __init__(
        self,
        chart_type: str = "bar",
        title: str = "",
        color: str = "gold",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._chart_type = chart_type
        self._title = title
        self._color = color
        self._x: list = []
        self._y: list = []
        self.add_class("chart-widget")

    def set_data(
        self,
        x: Optional[list] = None,
        y: Optional[list] = None,
        title: Optional[str] = None,
        color: Optional[str] = None,
    ):
        if x is not None:
            self._x = x
        if y is not None:
            self._y = y
        if title is not None:
            self._title = title
        if color is not None:
            self._color = color
        self.refresh()

    def render(self) -> str:
        plt.clear_figure()
        plt.title(self._title)
        # set a default plotsize; Textual will call render() again on resize
        plt.plotsize(self.size.width - 2, self.size.height - 3)

        if not self._x or not self._y:
            plt.plot([0], [0])
            return plt.build()

        if self._chart_type == "bar":
            plt.bar(self._x, self._y, color=self._color)
            plt.ylim(0, max(self._y) * 1.2 if self._y else 1)
        elif self._chart_type == "scatter":
            plt.scatter(self._x, self._y, color=self._color)
        else:
            # line / default
            plt.plot(self._x, self._y, color=self._color)

        return plt.build()
