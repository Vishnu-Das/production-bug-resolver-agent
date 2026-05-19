"""Deterministic routing guardrails for supervisor decisions."""

from __future__ import annotations

from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    EvidenceSourceType,
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

WORKFLOW_CONTROL_AGENT_NAMES = {
    AgentName.EVIDENCE_EVALUATOR,
    AgentName.RCA_WRITER,
    AgentName.SOLUTION_RECOMMENDER,
    AgentName.REPORT_WRITER,
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

        if (
            not state.evidence_items
            and not state.low_confidence
            and state.rca_report is None
            and decision.next_agent
            in {
                AgentName.EVIDENCE_EVALUATOR,
                AgentName.RCA_WRITER,
                AgentName.SOLUTION_RECOMMENDER,
                AgentName.REPORT_WRITER,
                AgentName.FINISH,
            }
        ):
            violated_rules.append("runtime_evidence_required_first")

        if not state.can_take_step():
            violated_rules.append("max_steps_reached")

        if not self._is_workflow_forced_control_decision(decision) and not state.can_invoke_agent(
            decision.next_agent
        ):
            violated_rules.append("max_agent_invocations_reached")

        if self._should_route_to_missing_code_evidence(state, decision):
            violated_rules.append("missing_code_evidence_should_route_to_code")

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

        # if not state.can_replan() and decision.next_agent in INVESTIGATION_AGENT_NAMES:
        #     if state.evidence_evaluation is not None:
        #         if state.evidence_evaluation.can_write_rca:
        #             violated_rules.append("max_replans_reached")
        #         elif not state.can_take_step():
        #             violated_rules.append("max_replans_reached")

        if violated_rules:
            return GuardrailDecision(
                guardrail_id=new_guardrail_id(),
                allowed=False,
                reason=self._blocked_reason(violated_rules),
                fallback_next_agent=self._fallback_agent(
                    blocked_agent=decision.next_agent,
                    state=state,
                ),
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
        # Workflow-forced control steps are intentionally repeated.
        #
        # Example:
        # log_investigator -> evidence_evaluator
        # code_investigator -> evidence_evaluator
        # knowledge_base_investigator -> evidence_evaluator
        #
        # The repeated-call guardrail is meant to stop the supervisor from
        # repeatedly choosing the same investigation agent with no new reason.
        # It should not block deterministic workflow control steps.
        if self._is_workflow_forced_control_decision(decision):
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

    def _is_workflow_forced_control_decision(self, decision: AgentDecision) -> bool:
        return (
            decision.metadata.get("forced_by_workflow") == "true"
            and decision.next_agent in WORKFLOW_CONTROL_AGENT_NAMES
        )

    def _should_route_to_missing_code_evidence(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        if self._is_workflow_forced_control_decision(decision):
            return False

        if decision.next_agent == AgentName.CODE_INVESTIGATOR:
            return False

        if not state.can_invoke_agent(AgentName.CODE_INVESTIGATOR):
            return False

        if state.evidence_evaluation is None:
            return False

        if state.evidence_evaluation.can_write_rca:
            return False

        source_types = {evidence.source_type for evidence in state.evidence_items}
        if EvidenceSourceType.CODE in source_types:
            return False

        return any(
            "code evidence is missing" in missing_evidence.lower()
            for missing_evidence in state.evidence_evaluation.missing_evidence
        )

    def _fallback_agent(
        self,
        *,
        blocked_agent: AgentName,
        state: WorkflowState,
    ) -> AgentName:
        if not state.evidence_items:
            return AgentName.LOG_INVESTIGATOR

        if self._missing_code_evidence(state) and state.can_invoke_agent(
            AgentName.CODE_INVESTIGATOR
        ):
            return AgentName.CODE_INVESTIGATOR

        if blocked_agent == AgentName.FINISH:
            return AgentName.EVIDENCE_EVALUATOR

        if blocked_agent == AgentName.SOLUTION_RECOMMENDER:
            return AgentName.RCA_WRITER

        if blocked_agent == AgentName.REPORT_WRITER:
            return AgentName.SOLUTION_RECOMMENDER

        if blocked_agent == AgentName.RCA_WRITER:
            return AgentName.EVIDENCE_EVALUATOR

        if blocked_agent in INVESTIGATION_AGENT_NAMES:
            return AgentName.EVIDENCE_EVALUATOR

        if blocked_agent == AgentName.EVIDENCE_EVALUATOR:
            return AgentName.FINISH

        return AgentName.EVIDENCE_EVALUATOR

    def _missing_code_evidence(self, state: WorkflowState) -> bool:
        if state.evidence_evaluation is None:
            return False

        if state.evidence_evaluation.can_write_rca:
            return False

        source_types = {evidence.source_type for evidence in state.evidence_items}
        if EvidenceSourceType.CODE in source_types:
            return False

        return any(
            "code evidence is missing" in missing_evidence.lower()
            for missing_evidence in state.evidence_evaluation.missing_evidence
        )

    def _can_finish(self, state: WorkflowState) -> bool:
        report_saved = state.report_save_result is not None or state.final_report_path is not None
        return report_saved or state.low_confidence

    def _blocked_reason(self, violated_rules: list[str]) -> str:
        return "Guardrail blocked routing decision: " + ", ".join(violated_rules)
