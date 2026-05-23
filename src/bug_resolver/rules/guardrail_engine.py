"""Deterministic routing guardrails for supervisor decisions."""

from __future__ import annotations

from bug_resolver.rules.guardrail_evidence_rules import GuardrailEvidenceRules
from bug_resolver.rules.guardrail_fallback_policy import GuardrailFallbackPolicy
from bug_resolver.rules.guardrail_graph_rules import GuardrailGraphRules
from bug_resolver.rules.guardrail_routing_rules import GuardrailRoutingRules
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    GuardrailDecision,
    WorkflowState,
)
from bug_resolver.utils.ids import new_guardrail_id


class GuardrailEngine:
    """
    Deterministic validation for supervisor routing decisions.

    This facade intentionally has no LLM dependency. Focused collaborators own
    routing, evidence, graph, and fallback policy details.
    """

    def __init__(
        self,
        routing_rules: GuardrailRoutingRules | None = None,
        evidence_rules: GuardrailEvidenceRules | None = None,
        graph_rules: GuardrailGraphRules | None = None,
        fallback_policy: GuardrailFallbackPolicy | None = None,
    ) -> None:
        self._routing_rules = routing_rules or GuardrailRoutingRules()
        self._evidence_rules = evidence_rules or GuardrailEvidenceRules(self._routing_rules)
        self._graph_rules = graph_rules or GuardrailGraphRules(self._evidence_rules)
        self._fallback_policy = fallback_policy or GuardrailFallbackPolicy(self._evidence_rules)

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
                AgentName.HISTORICAL_RCA_INVESTIGATOR,
                AgentName.PATCH_GENERATOR,
                AgentName.PATCH_SUGGESTER,
                AgentName.RCA_WRITER,
                AgentName.SOLUTION_RECOMMENDER,
                AgentName.REPORT_WRITER,
                AgentName.FINISH,
            }
        ):
            violated_rules.append("runtime_evidence_required_first")

        if not state.can_take_step():
            violated_rules.append("max_steps_reached")

        if (
            not self._routing_rules.is_workflow_forced_control_decision(decision)
            and not state.can_invoke_agent(decision.next_agent)
        ):
            violated_rules.append("max_agent_invocations_reached")

        if self._evidence_rules.should_route_to_missing_code_evidence(state, decision):
            violated_rules.append("missing_code_evidence_should_route_to_code")

        if self._routing_rules.repeated_agent_call_without_new_reason(state, decision):
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

        if decision.next_agent == AgentName.PATCH_SUGGESTER:
            if state.rca_report is None:
                violated_rules.append("patch_suggestion_requires_rca")
            if state.solution_recommendation is None:
                violated_rules.append("patch_suggestion_requires_solution")

        if decision.next_agent == AgentName.PATCH_GENERATOR:
            if state.rca_report is None:
                violated_rules.append("patch_generation_requires_rca")
            if state.solution_recommendation is None:
                violated_rules.append("patch_generation_requires_solution")
            if state.patch_suggestion is None:
                violated_rules.append("patch_generation_requires_patch_suggestion")

        if decision.next_agent == AgentName.FINISH:
            if not self._routing_rules.can_finish(state):
                violated_rules.append("finish_requires_report_or_low_confidence")

        if self._graph_rules.should_block_graph_before_code(state, decision):
            violated_rules.append("graph_investigator_requires_code_or_structural_signal")

        if violated_rules:
            return GuardrailDecision(
                guardrail_id=new_guardrail_id(),
                allowed=False,
                reason=self._routing_rules.blocked_reason(violated_rules),
                fallback_next_agent=self._fallback_policy.fallback_agent(
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
