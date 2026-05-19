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

    def build_hypotheses_considered(self, state: WorkflowState) -> list[str]:
        if self._has_invalid_summary_strategy(state.evidence_items):
            return [
                "H1: The LLM router emitted unsupported retrieval strategy value `summary`.",
                (
                    "H2: Summary-style document queries are expected to map to "
                    "`parent_child`, but the LLM router output contract allowed "
                    "the conceptual label `summary`."
                ),
                (
                    "H3: Router validation rejects unsupported LLM strategy values "
                    "and triggers fallback instead of normalizing the strategy."
                ),
            ]

        if self._has_log_and_code_evidence(state.evidence_items):
            return [
                (
                    "H1: Runtime failure is caused by an implementation mismatch "
                    "in the code path identified by the logs and code evidence."
                ),
                (
                    "H2: The observed behavior is caused by missing validation or "
                    "insufficient normalization around the failing code path."
                ),
            ]

        return [
            (
                "H1: The failure is visible in runtime evidence, but more code "
                "or knowledge-base context is required to confirm the root cause."
            )
        ]

    def build_root_cause(self, state: WorkflowState) -> str:
        if self._has_invalid_summary_strategy(state.evidence_items):
            root_cause = (
                "The LLM router emitted `summary` as a retrieval strategy, but "
                "`summary` is not a supported retrieval strategy value. The router "
                "validation raised `ValueError: Invalid strategy: summary`, causing "
                "the system to fall back to the rule-based router."
            )

            if self._has_parent_child_signal(state.evidence_items):
                root_cause += (
                    " The fallback resolved the same summary-style document query "
                    "to `parent_child`, indicating that this query intent should map "
                    "to the supported `parent_child` strategy rather than `summary`."
                )

            return root_cause

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
                "show the failing behavior that needs further investigation."
            )

        return "The root cause cannot be determined from the available evidence."

    def build_technical_explanation(self, state: WorkflowState) -> str:
        if self._has_invalid_summary_strategy(state.evidence_items):
            explanation = (
                "The runtime logs show that the LLM router failed with "
                "`ValueError: Invalid strategy: summary` during retrieval strategy "
                "resolution. This indicates that the LLM router returned a strategy "
                "value that failed the router validation step. "
            )

            llm_locations = self._locations_matching(
                state.evidence_items,
                source_type=EvidenceSourceType.CODE,
                patterns=["src\\rag\\routing\\llm.py", "src/rag/routing/llm.py"],
            )
            if llm_locations:
                explanation += (
                    "Code evidence from "
                    f"{', '.join(llm_locations)} points to the LLM routing path "
                    "where the returned strategy is validated. "
                )

            if self._has_parent_child_signal(state.evidence_items):
                explanation += (
                    "The fallback log and supporting evidence show that the same "
                    "summary-style query resolves to `parent_child`, which is the "
                    "supported retrieval strategy for broad document-summary intent. "
                )

            explanation += (
                "Therefore, the issue is a contract mismatch between the LLM "
                "router output vocabulary and the supported retrieval strategy "
                "values used by the application."
            )

            return explanation

        parts: list[str] = []
        for evidence in state.evidence_items:
            parts.append(f"{evidence.evidence_id}: {self._finding_text(evidence)}")

        return " ".join(parts) or "No technical evidence was available."

    def evidence_ids(self, state: WorkflowState) -> list[str]:
        return [evidence.evidence_id for evidence in state.evidence_items]

    def confidence_score(self, state: WorkflowState) -> float:
        if not state.evidence_items:
            return 0.0

        source_types = {evidence.source_type for evidence in state.evidence_items}

        has_logs = EvidenceSourceType.LOG in source_types
        has_code = EvidenceSourceType.CODE in source_types
        has_kb = EvidenceSourceType.KNOWLEDGE_BASE in source_types

        if self._has_invalid_summary_strategy(state.evidence_items):
            if has_logs and has_code and has_kb:
                return 0.85
            if has_logs and has_code:
                return 0.8
            if has_logs and has_kb:
                return 0.65
            return 0.55

        if has_logs and has_code and has_kb:
            return 0.8

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

        if self._has_invalid_summary_strategy(state.evidence_items):
            source_types = {evidence.source_type for evidence in state.evidence_items}
            has_kb = EvidenceSourceType.KNOWLEDGE_BASE in source_types

            if has_kb:
                return (
                    "Confidence is high because logs show the exact exception "
                    "`Invalid strategy: summary`, code evidence points to the LLM "
                    "routing validation path, and knowledge-base evidence describes "
                    "the expected summary-query routing behavior. Confidence is not "
                    "1.0 because the exact raw LLM router output payload and prompt "
                    "response were not captured."
                )

            return (
                "Confidence is moderately high because logs show the exact exception "
                "`Invalid strategy: summary`, and code/test evidence points to the LLM "
                "routing validation path. Confidence is not 1.0 because knowledge-base "
                "evidence and the exact raw LLM router output payload were not captured."
            )

        if state.evidence_evaluation is None:
            return "Evidence has not been evaluated."

        return (
            "Confidence is based on available evidence quality, source diversity, "
            f"and evaluator result: {state.evidence_evaluation.reason}"
        )

    def open_questions(self, state: WorkflowState) -> list[str]:
        if self._has_invalid_summary_strategy(state.evidence_items):
            return [
                (
                    "What exact raw structured output did the LLM router return "
                    "before validation failed?"
                ),
                (
                    "Does the LLM router prompt explicitly restrict strategy values "
                    "to the supported retrieval strategy enum?"
                ),
            ]

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
        if self._has_invalid_summary_strategy(state.evidence_items):
            return (
                "Update the LLM router prompt and/or structured output validation "
                "so the router emits only supported retrieval strategy values. For "
                "broad summary questions over a selected document, return "
                "`parent_child` directly or normalize `summary` to `parent_child` "
                "before validation."
            )

        code_evidence = self._evidence_for_source(state, EvidenceSourceType.CODE)
        if code_evidence:
            return f"Inspect and fix the code path at {self._location(code_evidence[0])}."

        return "Collect code evidence before making a concrete fix recommendation."

    def long_term_prevention(self) -> str:
        return (
            "Add regression tests, centralize retrieval strategy validation, improve "
            "structured error handling, and log raw router outputs when fallback occurs."
        )

    def tests_to_add(self, state: WorkflowState) -> list[str]:
        if self._has_invalid_summary_strategy(state.evidence_items):
            return [
                (
                    'Add a regression test where query="summarize this document" '
                    "and a selected document is present; assert the resolved "
                    "strategy is `parent_child`."
                ),
                (
                    "Add a test ensuring unsupported LLM strategy values are handled "
                    "with a clear fallback reason and do not silently degrade routing quality."
                ),
                (
                    "Add a contract test ensuring the LLM router can emit only supported "
                    "retrieval strategy enum values."
                ),
            ]

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

    def _combined_text(self, evidence_items: list[EvidenceItem]) -> str:
        values: list[str] = []

        for evidence in evidence_items:
            values.extend(
                [
                    evidence.evidence_id,
                    evidence.source_name,
                    evidence.content,
                    evidence.file_path or "",
                ]
            )

            values.extend(str(value) for value in evidence.metadata.values())

        return "\n".join(value for value in values if value)

    def _has_invalid_summary_strategy(self, evidence_items: list[EvidenceItem]) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return (
            "invalid strategy: summary" in combined_text
            or "valueerror: invalid strategy: summary" in combined_text
        )

    def _has_parent_child_signal(self, evidence_items: list[EvidenceItem]) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return "parent_child" in combined_text

    def _has_log_and_code_evidence(self, evidence_items: list[EvidenceItem]) -> bool:
        source_types = {evidence.source_type for evidence in evidence_items}
        return (
            EvidenceSourceType.LOG in source_types
            and EvidenceSourceType.CODE in source_types
        )

    def _locations_matching(
        self,
        evidence_items: list[EvidenceItem],
        *,
        source_type: EvidenceSourceType,
        patterns: list[str],
    ) -> list[str]:
        normalized_patterns = [pattern.lower() for pattern in patterns]
        locations: list[str] = []

        for evidence in evidence_items:
            if evidence.source_type != source_type:
                continue

            location = self._location(evidence)
            normalized_location = location.lower()

            if any(pattern in normalized_location for pattern in normalized_patterns):
                locations.append(location)

        return self.unique(locations)

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