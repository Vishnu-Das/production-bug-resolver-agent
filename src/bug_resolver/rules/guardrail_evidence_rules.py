"""Evidence-precondition guardrail helpers."""

from __future__ import annotations

from bug_resolver.rules.guardrail_routing_rules import GuardrailRoutingRules
from bug_resolver.schemas import AgentDecision, AgentName, EvidenceSourceType, WorkflowState


class GuardrailEvidenceRules:
    """Evaluate evidence availability rules for supervisor routing decisions."""

    def __init__(self, routing_rules: GuardrailRoutingRules | None = None) -> None:
        self._routing_rules = routing_rules or GuardrailRoutingRules()

    def should_route_to_missing_code_evidence(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        if self._routing_rules.is_workflow_forced_control_decision(decision):
            return False

        if decision.next_agent == AgentName.CODE_INVESTIGATOR:
            return False

        if not state.can_invoke_agent(AgentName.CODE_INVESTIGATOR):
            return False

        if state.evidence_evaluation is None:
            return False

        if state.evidence_evaluation.can_write_rca:
            return False

        if self.has_code_evidence(state):
            return False

        if not self.missing_code_evidence(state):
            return False

        if decision.next_agent == AgentName.KNOWLEDGE_BASE_INVESTIGATOR:
            return self.has_knowledge_base_evidence(state)

        return True

    def should_block_non_recovery_specialist_route(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        """Reserve standalone graph and KB agents for evaluator-requested recovery."""
        if decision.next_agent == AgentName.GRAPH_INVESTIGATOR:
            return not self.missing_structural_graph_evidence(state)
        if decision.next_agent == AgentName.KNOWLEDGE_BASE_INVESTIGATOR:
            return not self.missing_knowledge_base_evidence(state)
        return False

    def missing_code_evidence(self, state: WorkflowState) -> bool:
        if state.evidence_evaluation is None:
            return False

        if state.evidence_evaluation.can_write_rca:
            return False

        if self.has_code_evidence(state):
            return False

        return any(
            "code evidence is missing" in missing_evidence.lower()
            for missing_evidence in state.evidence_evaluation.missing_evidence
        )

    def should_route_to_missing_knowledge_base_evidence(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        if self._routing_rules.is_workflow_forced_control_decision(decision):
            return False

        if decision.next_agent == AgentName.KNOWLEDGE_BASE_INVESTIGATOR:
            return False

        if (
            decision.next_agent == AgentName.GRAPH_INVESTIGATOR
            and self.missing_structural_graph_evidence(state)
        ):
            return False

        if not state.can_invoke_agent(AgentName.KNOWLEDGE_BASE_INVESTIGATOR):
            return False

        return self.missing_knowledge_base_evidence(state)

    def should_route_to_missing_structural_graph_evidence(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        if self._routing_rules.is_workflow_forced_control_decision(decision):
            return False

        if decision.next_agent == AgentName.GRAPH_INVESTIGATOR:
            return False

        if not state.can_invoke_agent(AgentName.GRAPH_INVESTIGATOR):
            return False

        return self.missing_structural_graph_evidence(state)

    def missing_knowledge_base_evidence(self, state: WorkflowState) -> bool:
        if state.evidence_evaluation is None:
            return False

        if state.evidence_evaluation.can_write_rca:
            return False

        if self.has_knowledge_base_evidence(state):
            return False

        return any(
            "knowledge-base evidence is missing" in missing_evidence.lower()
            for missing_evidence in state.evidence_evaluation.missing_evidence
        )

    def missing_structural_graph_evidence(self, state: WorkflowState) -> bool:
        if state.evidence_evaluation is None:
            return False

        if state.evidence_evaluation.can_write_rca:
            return False

        if self.has_graph_evidence(state):
            return False

        return any(
            "structural graph evidence is missing" in missing_evidence.lower()
            for missing_evidence in state.evidence_evaluation.missing_evidence
        )

    def has_code_evidence(self, state: WorkflowState) -> bool:
        return any(
            evidence.source_type == EvidenceSourceType.CODE
            for evidence in state.evidence_items
        )

    def has_knowledge_base_evidence(self, state: WorkflowState) -> bool:
        return any(
            evidence.source_type == EvidenceSourceType.KNOWLEDGE_BASE
            for evidence in state.evidence_items
        )

    def has_graph_evidence(self, state: WorkflowState) -> bool:
        return any(
            evidence.source_type == EvidenceSourceType.GRAPH
            for evidence in state.evidence_items
        )
