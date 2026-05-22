"""Deterministic rules for judging whether collected evidence is sufficient."""

from __future__ import annotations

import re

from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, WorkflowState
from bug_resolver.schemas.orchestration import AgentName


STRUCTURAL_RELATIONSHIP_TERMS = (
    "structural_hint",
    "caller chain",
    "call chain",
    "callers",
    "callees",
    "called_by",
    "called by",
    "config reader",
    "config-read relationship",
    "reads config",
    "which function reads",
    "which request path calls",
    "request path calls function",
    "imports",
    "imported_by",
    "imported by",
    "ownership",
    "class/function relationship",
)

PYTHON_PATH_PATTERN = re.compile(r"\b(?:src|tests|eval|app|services)/[A-Za-z0-9_./-]+\.py\b")
SYMBOL_REFERENCE_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b")
FUNCTION_CALL_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\(\)")
CONFIG_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


class EvidenceEvaluationRules:
    """
    Deterministic rules for deciding whether collected evidence is enough for RCA.

    These rules evaluate the live investigation state before RCA writing. They do
    not inspect or generate an RCA report.
    """

    def confidence_score(self, state: WorkflowState) -> float:
        source_types = self._source_types(state.evidence_items)
        if not source_types:
            return 0.0

        score = 0.25

        if EvidenceSourceType.LOG in source_types:
            score += 0.25

        if EvidenceSourceType.CODE in source_types:
            score += 0.30

        if EvidenceSourceType.KNOWLEDGE_BASE in source_types:
            score += 0.15

        extra_evidence_count = max(
            0,
            len(state.evidence_items) - state.minimum_evidence_count_before_rca,
        )
        score += min(0.05, extra_evidence_count * 0.02)

        return round(min(score, 1.0), 2)

    def can_write_rca(self, state: WorkflowState, confidence_score: float) -> bool:
        if len(state.evidence_items) < state.minimum_evidence_count_before_rca:
            return False

        if self.structural_graph_evidence_required(state):
            return False

        source_types = self._source_types(state.evidence_items)
        has_primary_evidence = (
            EvidenceSourceType.LOG in source_types or EvidenceSourceType.CODE in source_types
        )
        if not has_primary_evidence:
            return False

        return confidence_score >= state.confidence_threshold

    def retry_required(self, state: WorkflowState, can_write_rca: bool) -> bool:
        if self.structural_graph_evidence_required(state):
            return True

        return not can_write_rca and state.can_replan()

    def missing_evidence(self, state: WorkflowState) -> list[str]:
        missing: list[str] = []
        source_types = self._source_types(state.evidence_items)

        if not state.evidence_items:
            missing.append("No evidence has been collected yet.")

        if len(state.evidence_items) < state.minimum_evidence_count_before_rca:
            missing.append("Minimum evidence count has not been met before RCA writing.")

        if EvidenceSourceType.LOG not in source_types:
            missing.append("Runtime log evidence is missing.")

        if EvidenceSourceType.CODE not in source_types:
            missing.append("Implementation code evidence is missing.")

        if (
            EvidenceSourceType.CODE not in source_types
            and self._has_structural_relationship_signal(state)
        ):
            missing.append(
                "Implementation code evidence is needed before structural graph investigation."
            )

        if (
            EvidenceSourceType.KNOWLEDGE_BASE not in source_types
            and EvidenceSourceType.CODE not in source_types
        ):
            missing.append(
                "Design or knowledge-base evidence may be needed to clarify expected behavior."
            )

        if self.structural_graph_evidence_required(state):
            missing.append("Structural graph evidence is missing.")

        if not state.can_replan() and missing:
            missing.append("Maximum replans have been reached.")

        return self.unique(missing)

    def conflicting_evidence(self, state: WorkflowState) -> list[str]:
        # Deterministic MVP version does not detect conflicts yet.
        return []

    def improved_code_queries(self, state: WorkflowState) -> list[str]:
        if EvidenceSourceType.CODE in self._source_types(state.evidence_items):
            return []

        queries = [
            state.incident.title,
            state.incident.description,
        ]

        for evidence in state.evidence_items:
            if evidence.source_type == EvidenceSourceType.LOG:
                queries.append(evidence.content)

        return self.unique(queries)

    def improved_knowledge_queries(self, state: WorkflowState) -> list[str]:
        if EvidenceSourceType.KNOWLEDGE_BASE in self._source_types(state.evidence_items):
            return []

        queries = [
            f"{state.incident.title} expected behavior",
            f"{state.incident.title} design documentation",
        ]

        if state.incident.affected_service:
            queries.append(f"{state.incident.affected_service} architecture")

        return self.unique(queries)

    def reason(
        self,
        *,
        state: WorkflowState,
        can_write_rca: bool,
        retry_required: bool,
    ) -> str:
        if can_write_rca:
            return "Evidence is sufficient to proceed to RCA writing."

        if self.structural_graph_evidence_required(state):
            return (
                "Structural relationship evidence is needed before RCA because "
                "the incident context asks for caller/callee, config-reader, import, "
                "ownership, or class/function relationship details."
            )

        if (
            EvidenceSourceType.CODE not in self._source_types(state.evidence_items)
            and self._has_structural_relationship_signal(state)
        ):
            return (
                "Implementation code evidence is needed before structural graph "
                "investigation can answer caller/callee, config-reader, import, "
                "ownership, or class/function relationship questions."
            )

        if retry_required:
            return "Evidence is incomplete; supervisor should replan for more evidence."

        return (
            "Evidence is incomplete, but replanning is no longer available under "
            "the configured limits."
        )

    def _source_types(self, evidence_items: list[EvidenceItem]) -> set[EvidenceSourceType]:
        return {evidence.source_type for evidence in evidence_items}

    def structural_graph_evidence_required(self, state: WorkflowState) -> bool:
        source_types = self._source_types(state.evidence_items)
        if EvidenceSourceType.CODE not in source_types:
            return False

        if EvidenceSourceType.GRAPH in source_types:
            return False

        if AgentName.GRAPH_INVESTIGATOR not in state.allowed_agent_names:
            return False

        if not state.can_invoke_agent(AgentName.GRAPH_INVESTIGATOR):
            return False

        return self._has_structural_relationship_signal(state)

    def _has_structural_relationship_signal(self, state: WorkflowState) -> bool:
        text = self._structural_signal_text(state)
        normalized = text.lower()

        if any(term in normalized for term in STRUCTURAL_RELATIONSHIP_TERMS):
            return True

        has_relationship_language = any(
            term in normalized
            for term in (
                "call",
                "calls",
                "called",
                "reader",
                "reads",
                "relationship",
                "import",
                "ownership",
                "path",
            )
        )

        if not has_relationship_language:
            return False

        return any(
            pattern.search(text)
            for pattern in (
                PYTHON_PATH_PATTERN,
                SYMBOL_REFERENCE_PATTERN,
                FUNCTION_CALL_PATTERN,
                CONFIG_KEY_PATTERN,
            )
        )

    def _structural_signal_text(self, state: WorkflowState) -> str:
        values = [
            state.incident.title,
            state.incident.description,
            state.incident.affected_service or "",
            state.incident.affected_area or "",
            state.incident.raw_input or "",
            *state.incident.metadata.keys(),
            *state.incident.metadata.values(),
        ]

        for evidence in state.evidence_items:
            values.extend(
                [
                    evidence.evidence_id,
                    evidence.source_name,
                    evidence.file_path or "",
                    evidence.content,
                    *evidence.metadata.keys(),
                    *evidence.metadata.values(),
                ]
            )

        return "\n".join(values)

    def unique(self, values: list[str] | object) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                continue

            normalized = value.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            unique_values.append(normalized)

        return unique_values
