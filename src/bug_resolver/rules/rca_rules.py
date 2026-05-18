from __future__ import annotations

from bug_resolver.schemas import (
    CodeContext,
    Hypothesis,
    Incident,
    KnowledgeContext,
    LogAnalysisResult,
)


class RCARules:
    """
    Deterministic rules for building an RCA report from hypotheses and evidence.

    The agent coordinates.
    These rules select the strongest hypothesis and build report sections.
    """

    confidence_threshold = 0.75

    def select_strongest_hypothesis(
        self,
        hypotheses: list[Hypothesis],
    ) -> Hypothesis:
        return sorted(
            hypotheses,
            key=lambda hypothesis: hypothesis.confidence_score,
            reverse=True,
        )[0]

    def build_title(self, incident: Incident) -> str:
        return f"RCA for {incident.title}"

    def build_incident_summary(self, incident: Incident) -> str:
        return (
            f"Incident {incident.incident_id}: {incident.description}"
        )

    def build_impact(self, incident: Incident) -> str | None:
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

    def build_symptoms(
        self,
        incident: Incident,
        log_analysis: LogAnalysisResult,
    ) -> list[str]:
        symptoms = [incident.description]

        if log_analysis.exception_type and log_analysis.exception_message:
            symptoms.append(
                f"{log_analysis.exception_type}: {log_analysis.exception_message}"
            )

        if log_analysis.likely_failure_point:
            symptoms.append(
                f"Likely failure point: {log_analysis.likely_failure_point}"
            )

        return self.unique(symptoms)

    def build_log_findings(
        self,
        log_analysis: LogAnalysisResult,
    ) -> list[str]:
        findings: list[str] = [log_analysis.summary]

        if log_analysis.exception_type:
            findings.append(f"Exception type: {log_analysis.exception_type}")

        if log_analysis.exception_message:
            findings.append(f"Exception message: {log_analysis.exception_message}")

        if log_analysis.likely_failure_point:
            findings.append(f"Likely failure point: {log_analysis.likely_failure_point}")

        if log_analysis.suspected_file_paths:
            findings.append(
                "Suspected files from logs: "
                + ", ".join(log_analysis.suspected_file_paths)
            )

        if log_analysis.suspected_function_names:
            findings.append(
                "Suspected functions from logs: "
                + ", ".join(log_analysis.suspected_function_names)
            )

        return self.unique(findings)

    def build_code_findings(
        self,
        code_contexts: list[CodeContext],
    ) -> list[str]:
        findings: list[str] = []

        for context in code_contexts:
            location = context.file_path

            if context.function_name:
                location = f"{location}::{context.function_name}"

            if context.line_start and context.line_end:
                location = f"{location}:{context.line_start}-{context.line_end}"

            findings.append(f"Retrieved code context from {location}.")

        return self.unique(findings)

    def build_knowledge_base_findings(
        self,
        knowledge_contexts: list[KnowledgeContext],
    ) -> list[str]:
        findings: list[str] = []

        for context in knowledge_contexts:
            location = context.document_name

            if context.section_title:
                location = f"{location}::{context.section_title}"

            findings.append(f"Retrieved knowledge-base context from {location}.")

        return self.unique(findings)

    def build_hypotheses_considered(
        self,
        hypotheses: list[Hypothesis],
    ) -> list[str]:
        return [
            (
                f"{hypothesis.hypothesis_id}: {hypothesis.title} "
                f"(confidence={hypothesis.confidence_score})"
            )
            for hypothesis in hypotheses
        ]

    def build_technical_explanation(
        self,
        selected_hypothesis: Hypothesis,
        log_analysis: LogAnalysisResult,
    ) -> str:
        parts = [
            selected_hypothesis.description,
            f"Suspected root cause: {selected_hypothesis.suspected_root_cause}",
        ]

        if log_analysis.likely_failure_point:
            parts.append(
                f"The runtime evidence points to {log_analysis.likely_failure_point}."
            )

        return " ".join(parts)

    def build_confidence_reason(
        self,
        selected_hypothesis: Hypothesis,
    ) -> str:
        if selected_hypothesis.confidence_score >= self.confidence_threshold:
            return (
                "Confidence is high enough because the selected hypothesis is "
                "supported by available evidence."
            )

        return (
            "Confidence is below threshold because available evidence is incomplete "
            "or does not fully prove the root cause."
        )

    def build_immediate_fix(
        self,
        selected_hypothesis: Hypothesis,
    ) -> str:
        return (
            "Inspect and fix the code path described by the selected hypothesis: "
            f"{selected_hypothesis.suspected_root_cause}"
        )

    def build_long_term_prevention(self) -> str:
        return (
            "Add regression tests, improve error handling, and improve logging around "
            "the failing code path."
        )

    def build_tests_to_add(
        self,
        incident: Incident,
        selected_hypothesis: Hypothesis,
    ) -> list[str]:
        tests = [
            f"Add a regression test for incident {incident.incident_id}.",
            "Add a test covering the selected failing code path.",
        ]

        if selected_hypothesis.supporting_evidence_ids:
            tests.append(
                "Add tests that verify behavior connected to the supporting evidence."
            )

        return tests

    def build_open_questions(
        self,
        selected_hypothesis: Hypothesis,
    ) -> list[str]:
        questions = list(selected_hypothesis.open_questions)

        if selected_hypothesis.confidence_score < self.confidence_threshold and not questions:
            questions.append(
                "What additional evidence is needed to confirm the root cause?"
            )

        return self.unique(questions)

    def build_low_confidence_warning(
        self,
        selected_hypothesis: Hypothesis,
    ) -> str | None:
        if selected_hypothesis.confidence_score >= self.confidence_threshold:
            return None

        return (
            "This RCA is low confidence because the selected hypothesis does not meet "
            "the confidence threshold."
        )

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