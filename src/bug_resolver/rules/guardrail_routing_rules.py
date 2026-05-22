"""Routing-level guardrail helpers for supervisor decisions."""

from __future__ import annotations

from bug_resolver.schemas import AgentDecision, AgentName, WorkflowState


INVESTIGATION_AGENT_NAMES = {
    AgentName.LOG_INVESTIGATOR,
    AgentName.CODE_INVESTIGATOR,
    AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
    AgentName.WEB_SEARCH_INVESTIGATOR,
    AgentName.GRAPH_INVESTIGATOR,
    AgentName.HISTORICAL_RCA_INVESTIGATOR,
}

WORKFLOW_CONTROL_AGENT_NAMES = {
    AgentName.EVIDENCE_EVALUATOR,
    AgentName.RCA_WRITER,
    AgentName.SOLUTION_RECOMMENDER,
    AgentName.REPORT_WRITER,
}


class GuardrailRoutingRules:
    """Evaluate generic routing rules that are not tied to one evidence source."""

    def is_workflow_forced_control_decision(self, decision: AgentDecision) -> bool:
        return (
            decision.metadata.get("forced_by_workflow") == "true"
            and decision.next_agent in WORKFLOW_CONTROL_AGENT_NAMES
        )

    def repeated_agent_call_without_new_reason(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        if self.is_workflow_forced_control_decision(decision):
            return False

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

    def can_finish(self, state: WorkflowState) -> bool:
        report_saved = state.report_save_result is not None or state.final_report_path is not None
        return report_saved or state.low_confidence

    def blocked_reason(self, violated_rules: list[str]) -> str:
        return "Guardrail blocked routing decision: " + ", ".join(violated_rules)
