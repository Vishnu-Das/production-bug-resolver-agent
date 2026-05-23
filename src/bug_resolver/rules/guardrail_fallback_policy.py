"""Fallback routing policy for blocked supervisor decisions."""

from __future__ import annotations

from bug_resolver.rules.guardrail_evidence_rules import GuardrailEvidenceRules
from bug_resolver.rules.guardrail_routing_rules import INVESTIGATION_AGENT_NAMES
from bug_resolver.schemas import AgentName, WorkflowState


class GuardrailFallbackPolicy:
    """Select a bounded fallback agent when a guardrail blocks a decision."""

    def __init__(self, evidence_rules: GuardrailEvidenceRules | None = None) -> None:
        self._evidence_rules = evidence_rules or GuardrailEvidenceRules()

    def fallback_agent(
        self,
        *,
        blocked_agent: AgentName,
        state: WorkflowState,
    ) -> AgentName:
        if not state.evidence_items:
            return AgentName.LOG_INVESTIGATOR

        if (
            blocked_agent == AgentName.GRAPH_INVESTIGATOR
            and state.can_invoke_agent(AgentName.CODE_INVESTIGATOR)
        ):
            return AgentName.CODE_INVESTIGATOR

        if self._evidence_rules.missing_code_evidence(state) and state.can_invoke_agent(
            AgentName.CODE_INVESTIGATOR
        ):
            return AgentName.CODE_INVESTIGATOR

        if blocked_agent == AgentName.FINISH:
            return AgentName.EVIDENCE_EVALUATOR

        if blocked_agent == AgentName.SOLUTION_RECOMMENDER:
            return AgentName.RCA_WRITER

        if blocked_agent == AgentName.REPORT_WRITER:
            return AgentName.SOLUTION_RECOMMENDER

        if blocked_agent == AgentName.PATCH_SUGGESTER:
            return AgentName.SOLUTION_RECOMMENDER

        if blocked_agent == AgentName.RCA_WRITER:
            return AgentName.EVIDENCE_EVALUATOR

        if blocked_agent in INVESTIGATION_AGENT_NAMES:
            return AgentName.EVIDENCE_EVALUATOR

        if blocked_agent == AgentName.EVIDENCE_EVALUATOR:
            return AgentName.FINISH

        return AgentName.EVIDENCE_EVALUATOR
