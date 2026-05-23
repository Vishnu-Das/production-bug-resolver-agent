"""Analyze-only patch suggestion agent."""

from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.patch_suggestion_rules import PatchSuggestionRules
from bug_resolver.schemas import PatchSuggestion, RCAReport, SolutionRecommendation
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.utils.observability import get_logger


logger = get_logger(__name__)


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
        suggestion = self._rules.build_patch_suggestion(
            rca_report=input_data.rca_report,
            solution=input_data.solution_recommendation,
        )
        logger.info(
            "patch suggestion generated incident_id=%s affected_files=%s evidence_count=%s",
            suggestion.incident_id,
            suggestion.affected_files,
            len(suggestion.evidence_ids),
        )
        return suggestion
