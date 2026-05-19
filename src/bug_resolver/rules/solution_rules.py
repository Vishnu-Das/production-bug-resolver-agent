from __future__ import annotations

from bug_resolver.schemas import RCAReport


class SolutionRules:
    """
    Deterministic rules for turning an RCA report into solution recommendations.

    The agent coordinates.
    These rules build actionable analyze-only recommendations.
    """

    def build_summary(self, rca_report: RCAReport) -> str:
        return (
            "Recommended solution based on RCA "
            f"{rca_report.report_id}: {rca_report.root_cause}"
        )

    def build_immediate_steps(self, rca_report: RCAReport) -> list[str]:
        steps: list[str] = []

        if rca_report.immediate_fix:
            steps.append(rca_report.immediate_fix)
        else:
            steps.append(
                "Inspect the failing code path identified in the RCA and apply a scoped fix."
            )

        steps.append("Reproduce the incident locally using the same failure scenario.")
        steps.append("Verify the fix against the log symptoms and selected RCA evidence.")

        return self.unique(steps)

    def build_long_term_steps(self, rca_report: RCAReport) -> list[str]:
        steps: list[str] = []

        if rca_report.long_term_prevention:
            steps.append(rca_report.long_term_prevention)

        if self._is_invalid_summary_strategy_rca(rca_report):
            steps.append(
                "Keep the LLM router output schema, prompt instructions, and retrieval "
                "strategy enum in sync so unsupported conceptual labels cannot be emitted."
            )
            steps.append(
                "Document the supported retrieval strategies and the expected mapping "
                "for summary-style selected-document questions."
            )
        else:
            steps.append(
                "Add input and output contract checks around the implicated code path."
            )
            steps.append(
                "Document the expected behavior and failure mode for future incidents."
            )

        return self.unique(steps)

    def build_tests_to_add(self, rca_report: RCAReport) -> list[str]:
        tests = list(rca_report.tests_to_add)

        if not tests:
            tests.append("Add a regression test that reproduces the incident.")
            tests.append("Add a unit test for the suspected failing code path.")

        return self.unique(tests)

    def build_monitoring_improvements(self, rca_report: RCAReport) -> list[str]:
        if self._is_invalid_summary_strategy_rca(rca_report):
            improvements = [
                (
                    "Log the raw LLM router strategy value, normalized strategy value, "
                    "router type, fallback reason, request id, and trace id whenever "
                    "router fallback occurs."
                ),
                (
                    "Add a metric for unsupported LLM router strategy values so "
                    "`summary`-style contract drift is visible before it affects users."
                ),
            ]
        else:
            improvements = [
                "Add structured logging around the implicated code path.",
                "Log request or trace identifiers with the error when available.",
            ]

        if rca_report.low_confidence_warning:
            improvements.append(
                "Capture additional diagnostic logs because the current RCA is low confidence."
            )

        if not rca_report.log_findings:
            improvements.append(
                "Improve runtime logging so future incidents include clear failure signals."
            )

        return self.unique(improvements)

    def _is_invalid_summary_strategy_rca(self, rca_report: RCAReport) -> bool:
        combined_text = "\n".join(
            [
                rca_report.root_cause,
                rca_report.technical_explanation,
                rca_report.immediate_fix or "",
            ]
        ).lower()
        return "invalid strategy: summary" in combined_text

    def build_risk_notes(self, rca_report: RCAReport) -> list[str]:
        risks: list[str] = []

        if rca_report.low_confidence_warning:
            risks.append(rca_report.low_confidence_warning)

        if rca_report.open_questions:
            risks.append(
                "Some open questions remain, so the recommendation should be validated before implementation."
            )

        if not rca_report.evidence_ids:
            risks.append(
                "No supporting evidence IDs are attached to the RCA, so confidence in the recommendation is limited."
            )

        if rca_report.confidence_score < 0.75:
            risks.append(
                "RCA confidence is below the production threshold of 0.75."
            )

        return self.unique(risks)

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
