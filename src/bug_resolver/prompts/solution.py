"""Prompt helper for solution recommendation experiments."""

from __future__ import annotations

from bug_resolver.schemas import RCAReport, SolutionRecommendation


class SolutionPromptBuilder:
    """
    Standalone solution recommendation prompt template for prompt experiments.

    The production SolutionRecommendationAgent owns its runtime structured prompt
    directly; keep this helper for isolated prompt iteration and documentation.
    """

    def build_system_prompt(self) -> str:
        """Build the runtime solution writer system prompt."""
        return (
            "You write analyze-only production fix recommendations from RCA reports. "
            "Do not claim a fix has been applied. Do not invent evidence, files, "
            "owners, timelines, or implementation details. Reference only evidence "
            "IDs from the RCA."
        )

    def build_user_prompt(
        self,
        rca_report: RCAReport,
        deterministic_recommendation: SolutionRecommendation,
    ) -> str:
        """Build the runtime solution writer user prompt from RCA and baseline."""
        return (
            "Write a structured solution recommendation from this RCA.\n\n"
            f"Incident ID: {rca_report.incident_id}\n"
            f"RCA report ID: {rca_report.report_id}\n"
            f"Title: {rca_report.title}\n"
            f"Root cause: {rca_report.root_cause}\n"
            f"Technical explanation: {rca_report.technical_explanation}\n"
            "Graph findings:\n"
            f"{self._format_list(rca_report.graph_findings)}\n"
            f"Immediate fix baseline: {rca_report.immediate_fix or 'not specified'}\n"
            f"Long-term prevention baseline: "
            f"{rca_report.long_term_prevention or 'not specified'}\n"
            f"Tests baseline: {', '.join(rca_report.tests_to_add) or 'none'}\n"
            f"Open questions: {', '.join(rca_report.open_questions) or 'none'}\n"
            f"RCA confidence: {rca_report.confidence_score}\n"
            f"Allowed evidence IDs: {', '.join(rca_report.evidence_ids)}\n\n"
            "Deterministic baseline recommendation for grounding:\n"
            f"Summary: {deterministic_recommendation.summary}\n"
            "Immediate steps:\n"
            f"{chr(10).join(f'- {step}' for step in deterministic_recommendation.immediate_steps)}\n"
            "Long-term steps:\n"
            f"{chr(10).join(f'- {step}' for step in deterministic_recommendation.long_term_steps)}\n"
            "Monitoring improvements:\n"
            f"{chr(10).join(f'- {step}' for step in deterministic_recommendation.monitoring_improvements)}\n\n"
            "Return concrete immediate steps, long-term steps, tests to add, "
            "monitoring improvements, risk notes, confidence, and evidence IDs."
        )

    def build_prompt(self) -> str:
        """Build the short experimental solution prompt used outside runtime agents."""
        return (
            "Generate an analyze-only solution recommendation from the RCA. "
            "Include immediate steps, long-term prevention, tests to add, "
            "monitoring improvements, risks, confidence, and evidence IDs. "
            "Do not generate or apply code patches."
        )

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- None"
        return "\n".join(f"- {value}" for value in values)
