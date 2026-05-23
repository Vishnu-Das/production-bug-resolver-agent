"""Report store protocol for persisting investigation artifacts."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from bug_resolver.schemas import PatchSuggestion, RCAReport, SolutionRecommendation


@runtime_checkable
class ReportStore(Protocol):
    """Contract for persisting and loading investigation reports."""

    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
        patch_suggestion: PatchSuggestion | None = None,
    ) -> list[Path]:
        """
        Save an RCA report.

        Implementations may save Markdown, JSON, evidence files, or all of them.
        Returns the paths written by the store.
        """
        ...

    async def get_report(self, incident_id: str) -> RCAReport | None:
        """Load a previously saved RCA report if available."""
        ...
