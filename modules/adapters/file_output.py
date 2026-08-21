"""File-system output adapter implementing FileOutputPort.

Reproduces byte-identical behavior to the pre-extraction disk writes in
``ReportBuilder.save_report``/``build_match_report``, ``LLMAdvisor.advise``
and ``scripts/ask_coach.py``.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class LocalFileOutput:
    """Writes reports and LLM debug artifacts under ``output_dir`` (default ``reports/``)."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)

    def write_report(self, report: dict[str, Any], filename: str) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / filename
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)

    def write_ollama_response(self, puuid: str, prompt: str, raw: Any, model: str) -> None:
        out_dir = os.path.join(str(self.output_dir), "ollama_responses")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        fname = os.path.join(out_dir, f"{puuid}.txt")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"# captured_at: {ts}\n# model: {model}\n# prompt:\n")
            f.write(prompt + "\n\n# raw_response:\n")
            try:
                f.write(json.dumps(raw, ensure_ascii=False, indent=2))
            except Exception:
                f.write(str(raw))

    def write_coach_exchange(self, payload: dict[str, Any], ts: str) -> None:
        out_dir = os.path.join(str(self.output_dir), "ollama_responses")
        os.makedirs(out_dir, exist_ok=True)
        fname = os.path.join(out_dir, f"ask_coach_{ts}.json")
        with open(fname, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
