"""Deterministic rules for judging whether collected evidence is sufficient."""

from __future__ import annotations

import re

from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules
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
SIGNAL_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")

EXPECTED_BEHAVIOR_TERMS = (
    "expected behavior",
    "expected result",
    "actual result",
    "intended behavior",
    "behavior mismatch",
    "wrong result",
    "incorrect result",
    "quality degraded",
    "quality regression",
    "should",
    "must",
    "policy",
    "design",
    "spec",
    "specification",
    "requirement",
    "no exception",
    "no error",
    "still returns",
    "successful response",
    "after deployment",
    "deployment behavior",
    "configuration policy",
    "config policy",
    "silent fallback",
    "fallback behavior",
    "what should happen",
    "which strategy should",
)

HISTORICAL_RCA_TERMS = (
    "again",
    "recurring",
    "recurrence",
    "regression",
    "similar incident",
    "similar issue",
    "seen before",
    "happened before",
    "previous incident",
    "previous rca",
    "past incident",
    "known issue",
    "same failure",
    "same problem",
    "repeat incident",
    "repeated incident",
)


class EvidenceEvaluationRules:
    """
    Deterministic rules for deciding whether collected evidence is enough for RCA.

    These rules evaluate the live investigation state before RCA writing. They do
    not inspect or generate an RCA report.
    """

    def __init__(self, code_path_rules: CodeEvidencePathRules | None = None) -> None:
        self._code_path_rules = code_path_rules or CodeEvidencePathRules()

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

        if self.graph_discovered_code_evidence_required(state):
            return False

        if self.implementation_owner_evidence_required(state):
            return False

        if self.knowledge_base_evidence_required(state):
            return False

        if self.historical_rca_evidence_required(state):
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

        if self.graph_discovered_code_evidence_required(state):
            return True

        if self.implementation_owner_evidence_required(state):
            return True

        if self.knowledge_base_evidence_required(state):
            return True

        if self.historical_rca_evidence_required(state):
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

        if self.graph_discovered_code_evidence_required(state):
            missing.append(
                "Implementation code evidence is missing for graph-discovered source files."
            )

        if self.implementation_owner_evidence_required(state):
            missing.append(
                "Implementation owner source evidence is missing; current code evidence "
                "is limited to tests or supporting context."
            )

        if self.knowledge_base_evidence_required(state):
            missing.append(
                "Knowledge-base evidence is missing for expected behavior, policy, "
                "configuration, deployment, or quality expectations."
            )

        if self.historical_rca_evidence_required(state):
            missing.append(
                "Historical RCA evidence is missing for recurrence or similar-incident context."
            )

        if not state.can_replan() and missing:
            missing.append("Maximum replans have been reached.")

        return self.unique(missing)

    def conflicting_evidence(self, state: WorkflowState) -> list[str]:
        # Deterministic MVP version does not detect conflicts yet.
        return []

    def improved_code_queries(self, state: WorkflowState) -> list[str]:
        if (
            EvidenceSourceType.CODE in self._source_types(state.evidence_items)
            and not self.graph_discovered_code_evidence_required(state)
            and not self.implementation_owner_evidence_required(state)
        ):
            return []

        queries = [
            state.incident.title,
            state.incident.description,
        ]

        for evidence in state.evidence_items:
            if evidence.source_type == EvidenceSourceType.LOG:
                queries.append(evidence.content)
            if evidence.source_type == EvidenceSourceType.KNOWLEDGE_BASE:
                queries.extend(
                    [
                        evidence.source_name,
                        evidence.content,
                    ]
                )
            if evidence.source_type == EvidenceSourceType.GRAPH:
                queries.extend(
                    [
                        evidence.file_path or evidence.source_name,
                        evidence.content,
                        *evidence.metadata.values(),
                    ]
                )

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

        if self.graph_discovered_code_evidence_required(state):
            return (
                "Implementation code evidence is needed for graph-discovered source "
                "files before RCA or patch generation. Graph evidence can identify "
                "relationships, but exact code evidence is needed for implementation "
                "ownership."
            )

        if self.implementation_owner_evidence_required(state):
            return (
                "Implementation owner source evidence is needed before RCA or patch "
                "generation because tests, graph relationships, or support context do "
                "not prove which production file owns the behavior."
            )

        if self.knowledge_base_evidence_required(state):
            return (
                "Knowledge-base evidence is needed before RCA because the incident "
                "context indicates a behavior, policy, configuration, deployment, "
                "or quality expectation mismatch."
            )

        if self.historical_rca_evidence_required(state):
            return (
                "Historical RCA evidence is useful before RCA because the incident "
                "context suggests recurrence or similarity to a prior incident. "
                "Current logs and code remain the primary proof."
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

    def graph_discovered_code_evidence_required(self, state: WorkflowState) -> bool:
        source_types = self._source_types(state.evidence_items)
        if EvidenceSourceType.GRAPH not in source_types:
            return False

        if AgentName.CODE_INVESTIGATOR not in state.allowed_agent_names:
            return False

        if not state.can_invoke_agent(AgentName.CODE_INVESTIGATOR):
            return False

        code_paths = self._code_evidence_paths(state)
        implementation_code_paths = {
            path for path in code_paths if not self._code_path_rules.is_support_path(path)
        }
        if implementation_code_paths:
            return False

        return bool(self._graph_source_paths(state) - code_paths)

    def implementation_owner_evidence_required(self, state: WorkflowState) -> bool:
        source_types = self._source_types(state.evidence_items)
        if EvidenceSourceType.CODE not in source_types:
            return False

        if AgentName.CODE_INVESTIGATOR not in state.allowed_agent_names:
            return False

        if not state.can_invoke_agent(AgentName.CODE_INVESTIGATOR):
            return False

        code_paths = self._code_evidence_paths(state)
        if not code_paths:
            return False

        implementation_paths = {
            path for path in code_paths if not self._code_path_rules.is_support_path(path)
        }
        return not implementation_paths

    def knowledge_base_evidence_required(self, state: WorkflowState) -> bool:
        source_types = self._source_types(state.evidence_items)
        if EvidenceSourceType.KNOWLEDGE_BASE in source_types:
            return False

        if EvidenceSourceType.CODE not in source_types:
            return False

        if AgentName.KNOWLEDGE_BASE_INVESTIGATOR not in state.allowed_agent_names:
            return False

        if not state.can_invoke_agent(AgentName.KNOWLEDGE_BASE_INVESTIGATOR):
            return False

        return self._has_expected_behavior_signal(state)

    def historical_rca_evidence_required(self, state: WorkflowState) -> bool:
        source_types = self._source_types(state.evidence_items)
        if EvidenceSourceType.HISTORICAL_RCA in source_types:
            return False

        if EvidenceSourceType.CODE not in source_types:
            return False

        if AgentName.HISTORICAL_RCA_INVESTIGATOR not in state.allowed_agent_names:
            return False

        if not state.can_invoke_agent(AgentName.HISTORICAL_RCA_INVESTIGATOR):
            return False

        return self._has_historical_rca_signal(state)

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
        return self._state_signal_text(state)

    def _has_expected_behavior_signal(self, state: WorkflowState) -> bool:
        return self._has_signal_terms(self._state_signal_text(state), EXPECTED_BEHAVIOR_TERMS)

    def _has_historical_rca_signal(self, state: WorkflowState) -> bool:
        return self._has_signal_terms(self._state_signal_text(state), HISTORICAL_RCA_TERMS)

    def _code_evidence_paths(self, state: WorkflowState) -> set[str]:
        return {
            self._normalize_path(evidence.file_path or evidence.source_name)
            for evidence in state.evidence_items
            if evidence.source_type == EvidenceSourceType.CODE
            and (evidence.file_path or evidence.source_name)
        }

    def _graph_source_paths(self, state: WorkflowState) -> set[str]:
        return {
            self._normalize_path(evidence.file_path or evidence.source_name)
            for evidence in state.evidence_items
            if evidence.source_type == EvidenceSourceType.GRAPH
            and (evidence.file_path or evidence.source_name)
            and self._normalize_path(evidence.file_path or evidence.source_name).startswith(
                ("src/", "app/", "services/", "lib/")
            )
        }

    def _normalize_path(self, path: str) -> str:
        return path.replace("\\", "/").lower().strip()

    def _has_signal_terms(self, value: str, terms: tuple[str, ...]) -> bool:
        normalized = value.lower()
        tokens = set(SIGNAL_TOKEN_PATTERN.findall(normalized))
        return any(
            term in normalized if " " in term else term in tokens
            for term in terms
        )

    def _state_signal_text(self, state: WorkflowState) -> str:
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
