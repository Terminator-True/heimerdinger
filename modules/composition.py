"""Composition root: wires concrete adapters into domain services.

Swap adapters here (e.g. a Redis-backed RateLimiterPort at Hito 3) without
touching domain code.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from modules.adapters.file_output import LocalFileOutput
from modules.adapters.json_config import JsonConfigSource
from modules.coaching.service import CoachingService
from modules.data.report_builder import ReportBuilder
from modules.ingest.lib import ingest_player
from modules.llm.llm_advisor import LLMAdvisor


@dataclass
class Services:
    report_builder: ReportBuilder
    coaching_service: CoachingService
    llm_advisor: LLMAdvisor
    config_source: JsonConfigSource
    file_output: LocalFileOutput
    ingest_player: Callable[..., dict[str, Any]]


def build_services(output_dir: str = "reports") -> Services:
    file_output = LocalFileOutput(output_dir)
    return Services(
        report_builder=ReportBuilder(output_dir=output_dir, file_output=file_output),
        coaching_service=CoachingService(file_output=file_output),
        llm_advisor=LLMAdvisor(file_output=file_output),
        config_source=JsonConfigSource(),
        file_output=file_output,
        ingest_player=ingest_player,
    )
