from __future__ import annotations

from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, WorkflowState


class RCARules:
    """Deterministic RCA helpers for dynamic evidence-backed reports."""

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
        return self._findings_for_source(state.evidence_items, EvidenceSourceType.LOG)

    def build_code_findings(self, state: WorkflowState) -> list[str]:
        return self._findings_for_source(state.evidence_items, EvidenceSourceType.CODE)

    def build_knowledge_base_findings(self, state: WorkflowState) -> list[str]:
        return self._findings_for_source(
            state.evidence_items,
            EvidenceSourceType.KNOWLEDGE_BASE,
        )

    def build_root_cause(self, state: WorkflowState) -> str:
        code_evidence = self._evidence_for_source(state, EvidenceSourceType.CODE)
        log_evidence = self._evidence_for_source(state, EvidenceSourceType.LOG)

        if code_evidence and log_evidence:
            return (
                "The incident is most likely caused by the implementation behavior "
                f"shown in {self._location(code_evidence[0])}, matching the runtime "
                "failure observed in logs."
            )

        if code_evidence:
            return (
                "The incident is most likely caused by the implementation behavior "
                f"shown in {self._location(code_evidence[0])}."
            )

        if log_evidence:
            return (
                "The incident root cause is not fully confirmed, but runtime logs "
                "show the failing behavior that needs further investigation."
            )

        return "The root cause cannot be determined from the available evidence."

    def build_technical_explanation(self, state: WorkflowState) -> str:
        parts: list[str] = []

        for evidence in state.evidence_items:
            parts.append(f"{evidence.evidence_id}: {self._finding_text(evidence)}")

        return " ".join(parts) or "No technical evidence was available."

    def evidence_ids(self, state: WorkflowState) -> list[str]:
        return [evidence.evidence_id for evidence in state.evidence_items]

    def confidence_score(self, state: WorkflowState) -> float:
        if state.evidence_evaluation is not None:
            return state.evidence_evaluation.confidence_score
        return 0.0

    def confidence_reason(self, state: WorkflowState) -> str:
        if state.evidence_evaluation is None:
            return "Evidence has not been evaluated."

        return state.evidence_evaluation.reason

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
            return f"Inspect and fix the code path at {self._location(code_evidence[0])}."

        return "Collect code evidence before making a concrete fix recommendation."

    def long_term_prevention(self) -> str:
        return (
            "Add regression tests, improve structured error handling, and improve "
            "logging around the failing code path."
        )

    def tests_to_add(self, state: WorkflowState) -> list[str]:
        tests = [f"Add a regression test for incident {state.incident.incident_id}."]

        if self._evidence_for_source(state, EvidenceSourceType.CODE):
            tests.append("Add a test covering the implicated implementation path.")

        return tests

    def _findings_for_source(
        self,
        evidence_items: list[EvidenceItem],
        source_type: EvidenceSourceType,
    ) -> list[str]:
        return self.unique(
            [
                self._finding_text(evidence)
                for evidence in evidence_items
                if evidence.source_type == source_type
            ]
        )

    def _evidence_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
    ) -> list[EvidenceItem]:
        return [
            evidence
            for evidence in state.evidence_items
            if evidence.source_type == source_type
        ]

    def _finding_text(self, evidence: EvidenceItem) -> str:
        return f"Retrieved {evidence.source_type.value} evidence from {self._location(evidence)}."

    def _location(self, evidence: EvidenceItem) -> str:
        location = evidence.file_path or evidence.source_name
        if evidence.line_start and evidence.line_end:
            return f"{location}:{evidence.line_start}-{evidence.line_end}"
        return location

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
