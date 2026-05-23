"""Report writer agent that persists RCA and solution artifacts."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.reports.base import ReportStore
from bug_resolver.schemas import PatchSuggestion, RCAReport, SolutionRecommendation
from bug_resolver.schemas.common import StrictBaseModel


class ReportWriterInput(StrictBaseModel):
    """Input bundle for persisting RCA and optional solution artifacts."""

    report: RCAReport
    solution: SolutionRecommendation | None = None
    patch_suggestion: PatchSuggestion | None = None


class ReportWriterAgent(BaseAgent[ReportWriterInput, list[Path]]):
    """
    Coordinates final report persistence.

    The agent does not write files directly.
    It depends only on ReportStore.

    ReportStore decides whether to write Markdown, JSON, evidence files,
    solution files, or all of them.
    """

    name = "report_writer_agent"

    def __init__(self, report_store: ReportStore) -> None:
        self._report_store = report_store

    async def _run(self, input_data: ReportWriterInput) -> list[Path]:
        return await self._report_store.save_report(
            input_data.report,
            solution=input_data.solution,
            patch_suggestion=input_data.patch_suggestion,
        )

    def _validate_output(self, output: list[Path]) -> None:
        super()._validate_output(output)

        if not output:
            raise ValueError(f"{self.name} did not write any report files.")
