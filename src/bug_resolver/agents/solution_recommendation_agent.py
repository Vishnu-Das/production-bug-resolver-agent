from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.solution_rules import SolutionRules
from bug_resolver.schemas import RCAReport, SolutionRecommendation
from bug_resolver.utils.ids import new_recommendation_id


class SolutionRecommendationAgent(BaseAgent[RCAReport, SolutionRecommendation]):
    """
    Coordinates analyze-only solution recommendation generation.

    Current version is deterministic:
    - converts RCA fields into immediate steps
    - adds prevention steps
    - carries tests and evidence IDs forward
    - marks risks for low-confidence RCA reports
    """

    name = "solution_recommendation_agent"

    def __init__(self, rules: SolutionRules | None = None) -> None:
        self._rules = rules or SolutionRules()

    async def _run(self, input_data: RCAReport) -> SolutionRecommendation:
        return SolutionRecommendation(
            recommendation_id=new_recommendation_id(),
            incident_id=input_data.incident_id,
            rca_report_id=input_data.report_id,
            summary=self._rules.build_summary(input_data),
            immediate_steps=self._rules.build_immediate_steps(input_data),
            long_term_steps=self._rules.build_long_term_steps(input_data),
            tests_to_add=self._rules.build_tests_to_add(input_data),
            monitoring_improvements=self._rules.build_monitoring_improvements(input_data),
            risk_notes=self._rules.build_risk_notes(input_data),
            confidence_score=input_data.confidence_score,
            evidence_ids=input_data.evidence_ids,
        )