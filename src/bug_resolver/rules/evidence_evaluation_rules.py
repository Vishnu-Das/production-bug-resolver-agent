from __future__ import annotations

from bug_resolver.schemas import RCAReport


class EvidenceEvaluationRules:
    """
    Deterministic rules for deciding whether an RCA is sufficiently supported.

    The agent coordinates.
    These rules decide retry need, missing evidence, and improved retrieval hints.
    """

    confidence_threshold = 0.75

    def retry_required(self, rca_report: RCAReport) -> bool:
        if rca_report.confidence_score < self.confidence_threshold:
            return True

        if rca_report.low_confidence_warning:
            return True

        if not rca_report.evidence_ids:
            return True

        if self.missing_evidence(rca_report):
            return True

        return False

    def missing_evidence(self, rca_report: RCAReport) -> list[str]:
        missing: list[str] = []

        if not rca_report.evidence_ids:
            missing.append("RCA has no supporting evidence IDs.")

        if not rca_report.log_findings:
            missing.append("RCA has no log findings.")

        if not rca_report.code_findings:
            missing.append("RCA has no code findings.")

        if not rca_report.knowledge_base_findings:
            missing.append("RCA has no knowledge-base findings.")

        if not rca_report.selected_hypothesis_id:
            missing.append("RCA has no selected hypothesis.")

        if rca_report.confidence_score < self.confidence_threshold:
            missing.append("RCA confidence is below threshold.")

        if rca_report.open_questions:
            missing.append("RCA still has open questions.")

        return self.unique(missing)

    def conflicting_evidence(self, rca_report: RCAReport) -> list[str]:
        # Deterministic MVP version does not detect conflicts yet.
        # Later, LLM/structured evidence comparison can populate this.
        return []

    def improved_code_queries(self, rca_report: RCAReport) -> list[str]:
        queries: list[str] = []

        if rca_report.root_cause:
            queries.append(rca_report.root_cause)

        if rca_report.technical_explanation:
            queries.append(rca_report.technical_explanation)

        queries.extend(rca_report.symptoms)

        for question in rca_report.open_questions:
            if "source file" in question.lower() or "code" in question.lower():
                queries.append(question)

        if not rca_report.code_findings:
            queries.append("Find implementation code path related to the RCA root cause.")

        return self.unique(queries)

    def improved_knowledge_queries(self, rca_report: RCAReport) -> list[str]:
        queries: list[str] = []

        queries.extend(rca_report.symptoms)

        for question in rca_report.open_questions:
            if (
                "expected behavior" in question.lower()
                or "documentation" in question.lower()
                or "knowledge" in question.lower()
            ):
                queries.append(question)

        if not rca_report.knowledge_base_findings:
            queries.append("Find expected behavior or design documentation for this incident.")

        return self.unique(queries)

    def reason(self, rca_report: RCAReport, retry_required: bool) -> str:
        if retry_required:
            return (
                "Retry is required because the RCA is not sufficiently supported by "
                "the available evidence."
            )

        return (
            "Retry is not required because the RCA confidence meets the threshold "
            "and required evidence is present."
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