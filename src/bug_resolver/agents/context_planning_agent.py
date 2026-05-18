from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.context_planning_rules import ContextPlanningRules
from bug_resolver.schemas import ContextPlan, Incident, LogAnalysisResult
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.utils.ids import new_context_plan_id


class ContextPlanningInput(StrictBaseModel):
    incident: Incident
    log_analysis: LogAnalysisResult
    retry_reason: str | None = None
    previous_missing_evidence_hints: list[str] = Field(default_factory=list)


class ContextPlanningAgent(BaseAgent[ContextPlanningInput, ContextPlan]):
    """
    Coordinates context planning.

    This agent decides which code and knowledge-base searches should happen next.
    Deterministic planning rules live in ContextPlanningRules.
    """

    name = "context_planning_agent"

    def __init__(self, rules: ContextPlanningRules | None = None) -> None:
        self._rules = rules or ContextPlanningRules()

    async def _run(self, input_data: ContextPlanningInput) -> ContextPlan:
        incident = input_data.incident
        log_analysis = input_data.log_analysis

        missing_evidence_hints = self._rules.unique(
            [
                *self._rules.build_missing_evidence_hints(incident, log_analysis),
                *input_data.previous_missing_evidence_hints,
            ]
        )

        return ContextPlan(
            plan_id=new_context_plan_id(),
            code_search_queries=self._rules.build_code_search_queries(
                incident=incident,
                log_analysis=log_analysis,
            ),
            knowledge_search_queries=self._rules.build_knowledge_search_queries(
                incident=incident,
                log_analysis=log_analysis,
            ),
            files_to_prioritize=self._rules.files_to_prioritize(log_analysis),
            functions_to_prioritize=self._rules.functions_to_prioritize(log_analysis),
            missing_evidence_hints=missing_evidence_hints,
            retry_reason=input_data.retry_reason,
            generated_from=self._rules.build_generated_from(
                incident=incident,
                log_analysis=log_analysis,
            ),
            metadata={
                "incident_id": incident.incident_id,
            },
        )