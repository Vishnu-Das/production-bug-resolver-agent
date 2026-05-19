from __future__ import annotations

from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    GuardrailDecision,
    WorkflowState,
)
from bug_resolver.utils.ids import new_guardrail_id


INVESTIGATION_AGENT_NAMES = {
    AgentName.LOG_INVESTIGATOR,
    AgentName.CODE_INVESTIGATOR,
    AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
    AgentName.WEB_SEARCH_INVESTIGATOR,
    AgentName.GRAPH_INVESTIGATOR,
    AgentName.HISTORICAL_RCA_INVESTIGATOR,
}


class GuardrailEngine:
    """
    Deterministic validation for supervisor routing decisions.

    This engine intentionally has no LLM dependency. It only evaluates the
    current workflow state and the structured decision produced by the supervisor.
    """

    def validate_decision(
        self,
        *,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> GuardrailDecision:
        violated_rules: list[str] = []

        if decision.next_agent not in state.allowed_agent_names:
            violated_rules.append("unknown_or_disallowed_agent")

        if not state.can_take_step():
            violated_rules.append("max_steps_reached")

        if not state.can_invoke_agent(decision.next_agent):
            violated_rules.append("max_agent_invocations_reached")

        if self._is_repeated_agent_call_without_new_reason(state, decision):
            violated_rules.append("repeated_agent_call_without_new_reason")

        if decision.next_agent == AgentName.RCA_WRITER:
            if not state.has_minimum_evidence_for_rca() and state.can_take_step():
                violated_rules.append("minimum_evidence_not_met_for_rca")

        if decision.next_agent == AgentName.SOLUTION_RECOMMENDER:
            if state.rca_report is None:
                violated_rules.append("solution_requires_rca")

        if decision.next_agent == AgentName.REPORT_WRITER:
            if state.rca_report is None:
                violated_rules.append("report_requires_rca")
            if state.solution_recommendation is None:
                violated_rules.append("report_requires_solution")

        if decision.next_agent == AgentName.FINISH:
            if not self._can_finish(state):
                violated_rules.append("finish_requires_report_or_low_confidence")

        if not state.can_replan() and decision.next_agent in INVESTIGATION_AGENT_NAMES:
            if state.evidence_evaluation is not None:
                violated_rules.append("max_replans_reached")

        if violated_rules:
            return GuardrailDecision(
                guardrail_id=new_guardrail_id(),
                allowed=False,
                reason=self._blocked_reason(violated_rules),
                fallback_next_agent=self._fallback_agent(decision.next_agent),
                violated_rules=violated_rules,
            )

        return GuardrailDecision(
            guardrail_id=new_guardrail_id(),
            allowed=True,
            reason=f"Routing to {decision.next_agent.value} is allowed.",
        )

    def _is_repeated_agent_call_without_new_reason(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        previous_decisions = [
            previous_decision
            for previous_decision in state.trace.decisions
            if previous_decision.next_agent == decision.next_agent
            and previous_decision.decision_id != decision.decision_id
        ]
        if not previous_decisions:
            return False

        previous_decision = previous_decisions[-1]
        return (
            previous_decision.reason == decision.reason
            and previous_decision.queries == decision.queries
        )

    def _fallback_agent(self, blocked_agent: AgentName) -> AgentName:
        if blocked_agent == AgentName.FINISH:
            return AgentName.EVIDENCE_EVALUATOR

        if blocked_agent == AgentName.SOLUTION_RECOMMENDER:
            return AgentName.RCA_WRITER

        if blocked_agent == AgentName.REPORT_WRITER:
            return AgentName.SOLUTION_RECOMMENDER

        if blocked_agent in {
            AgentName.RCA_WRITER,
        }:
            return AgentName.EVIDENCE_EVALUATOR

        return AgentName.FINISH

    def _can_finish(self, state: WorkflowState) -> bool:
        report_saved = (
            state.report_save_result is not None
            or state.final_report_path is not None
        )
        return report_saved or state.low_confidence

    def _blocked_reason(self, violated_rules: list[str]) -> str:
        return "Guardrail blocked routing decision: " + ", ".join(violated_rules)
