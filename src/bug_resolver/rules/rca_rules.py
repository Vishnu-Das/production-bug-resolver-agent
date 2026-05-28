"""Deterministic RCA construction helpers."""

from __future__ import annotations

from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules
from bug_resolver.rules.evidence_formatting_rules import EvidenceFormattingRules
from bug_resolver.rules.evidence_selection_rules import EvidenceSelectionRules
from bug_resolver.rules.rca_evidence_selection_rules import RCAEvidenceSelectionRules
from bug_resolver.rules.rca_finding_rules import RCAFindingRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, WorkflowState


class RCARules:
    """Build generic evidence-backed RCA fields without repo-specific vocabulary."""

    def __init__(
        self,
        evidence_selection_rules: EvidenceSelectionRules | None = None,
        code_path_rules: CodeEvidencePathRules | None = None,
        formatter: EvidenceFormattingRules | None = None,
        finding_rules: RCAFindingRules | None = None,
        evidence_selection: RCAEvidenceSelectionRules | None = None,
    ) -> None:
        self.evidence_selection_rules = evidence_selection_rules or EvidenceSelectionRules()
        self.code_path_rules = code_path_rules or CodeEvidencePathRules()
        self.formatter = formatter or EvidenceFormattingRules()
        self.finding_rules = finding_rules or RCAFindingRules(
            formatter=self.formatter,
            evidence_selection_rules=self.evidence_selection_rules,
        )
        self.evidence_selection = evidence_selection or RCAEvidenceSelectionRules(
            evidence_selection_rules=self.evidence_selection_rules,
            code_path_rules=self.code_path_rules,
            formatter=self.formatter,
        )

    def build_title(self, state: WorkflowState) -> str:
        return f"RCA for {state.incident.title}"

    def build_incident_summary(self, state: WorkflowState) -> str:
        return f"Incident {state.incident.incident_id}: {state.incident.description}"

    def build_impact(self, state: WorkflowState) -> str | None:
        incident = state.incident
        if incident.affected_service and incident.affected_area:
            return (
                f"Affected service: {incident.affected_service}. "
                f"Affected area: {incident.affected_area}."
            )

        if incident.affected_service:
            return f"Affected service: {incident.affected_service}."

        if incident.affected_area:
            return f"Affected area: {incident.affected_area}."

        return None

    def build_symptoms(self, state: WorkflowState) -> list[str]:
        symptoms = [state.incident.description]
        symptoms.extend(
            evidence.content
            for evidence in state.evidence_items
            if evidence.source_type == EvidenceSourceType.LOG
        )
        return self.unique(symptoms)

    def build_log_findings(self, state: WorkflowState) -> list[str]:
        return self.finding_rules.findings_for_source(
            state.evidence_items,
            EvidenceSourceType.LOG,
        )

    def build_code_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(state, EvidenceSourceType.CODE, max_findings=3)

    def build_graph_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(
            state,
            EvidenceSourceType.GRAPH,
            max_findings=2,
        )

    def build_knowledge_base_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(
            state,
            EvidenceSourceType.KNOWLEDGE_BASE,
            max_findings=2,
        )

    def build_historical_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(
            state,
            EvidenceSourceType.HISTORICAL_RCA,
            max_findings=2,
        )

    def build_hypotheses_considered(self, state: WorkflowState) -> list[str]:
        if self._has_log_and_code_evidence(state.evidence_items):
            return [
                (
                    "H1: The runtime failure is caused by the implementation behavior "
                    "identified by the strongest log and code evidence."
                ),
                (
                    "H2: The observed behavior is caused by missing validation, "
                    "normalization, or error handling near the implicated code path."
                ),
            ]

        if self._evidence_for_source(state, EvidenceSourceType.LOG):
            return [
                (
                    "H1: Runtime evidence identifies the failing behavior, but code "
                    "owner evidence is still needed to confirm the root cause."
                )
            ]

        return [
            (
                "H1: The incident needs stronger runtime and implementation evidence "
                "before a concrete root-cause hypothesis can be confirmed."
            )
        ]

    def selected_hypothesis_id(self, state: WorkflowState) -> str:
        return "H1"

    def build_root_cause(self, state: WorkflowState) -> str:
        code_evidence = self._evidence_for_source(state, EvidenceSourceType.CODE)
        log_evidence = self._evidence_for_source(state, EvidenceSourceType.LOG)

        if code_evidence and log_evidence:
            return (
                "The incident is most likely caused by a mismatch between the "
                "runtime failure observed in logs and the implementation behavior "
                f"shown in {self._location(code_evidence[0])}."
            )

        if code_evidence:
            return (
                "The incident is most likely caused by the implementation behavior "
                f"shown in {self._location(code_evidence[0])}."
            )

        if log_evidence:
            return (
                "The incident root cause is not fully confirmed, but runtime logs "
                "show the failing behavior that needs code-owner investigation."
            )

        return "The root cause cannot be determined from the available evidence."

    def build_technical_explanation(self, state: WorkflowState) -> str:
        parts: list[str] = []
        for evidence in state.evidence_items:
            parts.append(f"{evidence.evidence_id}: {self._finding_text(evidence)}")

        return " ".join(parts) or "No technical evidence was available."

    def evidence_ids(self, state: WorkflowState) -> list[str]:
        return self.evidence_selection.evidence_ids(state)

    def confidence_score(self, state: WorkflowState) -> float:
        if not state.evidence_items:
            return 0.0

        source_types = {evidence.source_type for evidence in state.evidence_items}
        has_logs = EvidenceSourceType.LOG in source_types
        has_code = EvidenceSourceType.CODE in source_types
        has_kb = EvidenceSourceType.KNOWLEDGE_BASE in source_types
        has_graph = EvidenceSourceType.GRAPH in source_types

        if has_logs and has_code and has_kb:
            return 0.8

        if has_logs and has_code and has_graph:
            return 0.78

        if has_logs and has_code:
            return 0.75

        if has_logs and has_kb:
            return 0.65

        if has_logs:
            return 0.5

        if state.evidence_evaluation is not None:
            return min(state.evidence_evaluation.confidence_score, 0.8)

        return 0.4

    def confidence_reason(self, state: WorkflowState) -> str:
        if not state.evidence_items:
            return "No evidence was collected."

        if state.evidence_evaluation is None:
            return (
                "Confidence is based on available evidence source diversity and "
                "whether runtime evidence is connected to readable implementation evidence."
            )

        return (
            "Confidence is based on available evidence quality, source diversity, "
            f"and evaluator result: {state.evidence_evaluation.reason}"
        )

    def open_questions(self, state: WorkflowState) -> list[str]:
        if state.evidence_evaluation is None:
            return ["What additional evidence is needed to confirm the root cause?"]

        if state.evidence_evaluation.can_write_rca:
            return []

        return state.evidence_evaluation.missing_evidence or [
            "What additional evidence is needed to confirm the root cause?"
        ]

    def low_confidence_warning(self, state: WorkflowState) -> str | None:
        confidence_score = self.confidence_score(state)
        if confidence_score >= state.confidence_threshold:
            return None

        return (
            "This RCA is low confidence because collected evidence does not meet "
            "the configured confidence threshold."
        )

    def immediate_fix(self, state: WorkflowState) -> str:
        code_evidence = self._evidence_for_source(state, EvidenceSourceType.CODE)
        if code_evidence:
            return (
                "Inspect the implicated implementation path, reproduce the failure, "
                f"and apply a scoped fix at {self._location(code_evidence[0])}."
            )

        return "Collect code-owner evidence before making a concrete fix recommendation."

    def long_term_prevention(self) -> str:
        return (
            "Add regression coverage for the confirmed failure mode, validate the "
            "affected input/output contract, and improve structured diagnostic logging "
            "around the implicated code path."
        )

    def tests_to_add(self, state: WorkflowState) -> list[str]:
        tests = [f"Add a regression test for incident {state.incident.incident_id}."]

        if self._evidence_for_source(state, EvidenceSourceType.CODE):
            tests.append("Add a unit or integration test covering the implicated code path.")

        if self._evidence_for_source(state, EvidenceSourceType.LOG):
            tests.append("Add a test that reproduces the runtime symptom captured in logs.")

        return self.unique(tests)

    def _findings_for_source(
        self,
        evidence_items: list[EvidenceItem],
        source_type: EvidenceSourceType,
    ) -> list[str]:
        return self.finding_rules.findings_for_source(evidence_items, source_type)

    def _selected_findings_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
        *,
        max_findings: int,
    ) -> list[str]:
        selected_items = self._selected_evidence_for_source(
            state,
            source_type,
            max_items=max_findings,
        )

        return self.unique(
            [self.finding_rules.finding_text(evidence) for evidence in selected_items]
        )

    def _selected_evidence_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
        *,
        max_items: int,
    ) -> list[EvidenceItem]:
        return self.evidence_selection.selected_evidence_for_source(
            state,
            source_type,
            max_items=max_items,
        )

    def _prefer_primary_code_evidence(
        self,
        evidence_items: list[EvidenceItem],
        incident_terms: set[str],
    ) -> list[EvidenceItem]:
        return self.evidence_selection._prefer_primary_code_evidence(
            evidence_items,
            incident_terms,
        )

    def _evidence_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
    ) -> list[EvidenceItem]:
        return self.evidence_selection.evidence_for_source(state, source_type)

    def _finding_text(self, evidence: EvidenceItem) -> str:
        return self.finding_rules.finding_text(evidence)

    def _shorten(self, value: str, *, max_length: int = 180) -> str:
        return self.formatter.shorten(value, max_length=max_length)

    def _location(self, evidence: EvidenceItem) -> str:
        return self.formatter.location(evidence)

    def _symbol_name(self, evidence: EvidenceItem) -> str | None:
        return self.formatter.symbol_name(evidence)

    def _display_path(self, path: str) -> str:
        return self.formatter.display_path(path)

    def _combined_text(self, evidence_items: list[EvidenceItem]) -> str:
        return self.formatter.combined_text(evidence_items)

    def _has_log_and_code_evidence(self, evidence_items: list[EvidenceItem]) -> bool:
        source_types = {evidence.source_type for evidence in evidence_items}
        return EvidenceSourceType.LOG in source_types and EvidenceSourceType.CODE in source_types

    def _locations_matching(
        self,
        evidence_items: list[EvidenceItem],
        *,
        source_type: EvidenceSourceType,
        patterns: list[str],
    ) -> list[str]:
        return self.formatter.locations_matching(
            evidence_items,
            source_type=source_type,
            patterns=patterns,
        )

    def unique(self, values: list[str] | object) -> list[str]:
        return self.formatter.unique(values)
