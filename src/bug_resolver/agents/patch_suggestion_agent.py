"""Analyze-only patch suggestion agent."""

from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.patch_suggestion_rules import PatchSuggestionRules
from bug_resolver.schemas import PatchSuggestion, RCAReport, SolutionRecommendation
from bug_resolver.schemas.common import StrictBaseModel


class PatchSuggestionInput(StrictBaseModel):
    """Input bundle for generating a patch suggestion."""

    rca_report: RCAReport
    solution_recommendation: SolutionRecommendation


class PatchSuggestionAgent(BaseAgent[PatchSuggestionInput, PatchSuggestion]):
    """Builds a human-reviewable patch plan without changing code."""

    name = "patch_suggestion_agent"

    def __init__(self, rules: PatchSuggestionRules | None = None) -> None:
        self._rules = rules or PatchSuggestionRules()

    async def _run(self, input_data: PatchSuggestionInput) -> PatchSuggestion:
        return self._rules.build_patch_suggestion(
            rca_report=input_data.rca_report,
            solution=input_data.solution_recommendation,
        )
