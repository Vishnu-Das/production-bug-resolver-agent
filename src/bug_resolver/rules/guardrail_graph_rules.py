"""Graph-investigator guardrail helpers."""

from __future__ import annotations

import re

from bug_resolver.rules.guardrail_evidence_rules import GuardrailEvidenceRules
from bug_resolver.schemas import AgentDecision, AgentName, EvidenceSourceType, WorkflowState


class GuardrailGraphRules:
    """Evaluate structural graph routing preconditions."""

    def __init__(self, evidence_rules: GuardrailEvidenceRules | None = None) -> None:
        self._evidence_rules = evidence_rules or GuardrailEvidenceRules()

    def should_block_graph_before_code(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        if decision.next_agent != AgentName.GRAPH_INVESTIGATOR:
            return False

        if self._evidence_rules.has_code_evidence(state):
            return False

        if self.has_strong_graph_anchor(state, decision):
            return False

        return True

    def has_strong_graph_anchor(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> bool:
        values: list[str] = [
            state.incident.title,
            state.incident.description,
            state.incident.affected_service or "",
            state.incident.affected_area or "",
            decision.reason,
            *decision.queries,
            *decision.expected_evidence,
        ]

        values.extend(
            str(value)
            for value in state.incident.metadata.values()
            if value is not None
        )

        values.extend(
            evidence.content
            for evidence in state.evidence_items
            if evidence.source_type == EvidenceSourceType.LOG
        )

        text = "\n".join(value for value in values if value)

        return (
            self.contains_python_file_path(text)
            or self.contains_config_key(text)
            or self.contains_symbol_reference(text)
        )

    def contains_python_file_path(self, text: str) -> bool:
        return bool(
            re.search(
                r"(?:^|[\s\"'`])[\w./\\-]+\.py(?::\d+)?",
                text,
            )
        )

    def contains_config_key(self, text: str) -> bool:
        return bool(
            re.search(
                r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+){1,}\b",
                text,
            )
        )

    def contains_symbol_reference(self, text: str) -> bool:
        return bool(
            re.search(
                r"\b[A-Z][A-Za-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]*\b",
                text,
            )
            or re.search(
                r"\b[a-z_][a-z0-9_]{2,}\([^)]*\)",
                text,
            )
        )
