"""Solution recommendation agent with LLM-first generation and deterministic fallback."""

from __future__ import annotations

import re

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.llm.base import LLMClient
from bug_resolver.rules.solution_rules import SolutionRules
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas import RCAReport, SolutionRecommendation
from bug_resolver.utils.ids import new_recommendation_id


ANALYZE_ONLY_FORBIDDEN_PHRASES = (
    "i fixed",
    "we fixed",
    "has been fixed",
    "was fixed",
    "is fixed",
    "deployed the fix",
    "deployed a fix",
    "merged the fix",
    "opened a pull request",
    "created a pull request",
)

EVIDENCE_ID_IN_PROSE_PATTERN = re.compile(
    r"\b(?:EVID-[A-Z0-9_-]+|EVIDENCE-[A-Za-z0-9_-]+|kb-[A-Za-z0-9_-]+|"
    r"evidence-[A-Za-z0-9_./\\:-]+)\b",
    re.IGNORECASE,
)


class SolutionRecommendationFallback(Exception):
    """Internal control exception carrying the deterministic fallback reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SolutionRecommendationOutput(StrictBaseModel):
    """Structured LLM response expected from the solution writer model."""

    summary: str = Field(..., min_length=1)
    immediate_steps: list[str]
    long_term_steps: list[str]
    tests_to_add: list[str]
    monitoring_improvements: list[str]
    risk_notes: list[str]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str]


class SolutionRecommendationAgent(BaseAgent[RCAReport, SolutionRecommendation]):
    """
    Coordinates analyze-only solution recommendation generation.

    The agent asks an LLM for a structured recommendation first, validates the
    output, and falls back to deterministic SolutionRules when validation fails.
    """

    name = "solution_recommendation_agent"

    def __init__(
        self,
        rules: SolutionRules | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._rules = rules or SolutionRules()
        self._llm_client = llm_client

    async def _run(self, input_data: RCAReport) -> SolutionRecommendation:
        deterministic_recommendation = self._build_deterministic_recommendation(input_data)

        if self._llm_client is None:
            return self._with_fallback_metadata(
                deterministic_recommendation,
                reason="llm_client_not_configured",
            )

        try:
            llm_output = await self._llm_client.generate_structured(
                self._build_prompt(input_data, deterministic_recommendation),
                SolutionRecommendationOutput,
                system_prompt=self._build_system_prompt(),
            )
        except Exception:
            return self._with_fallback_metadata(
                deterministic_recommendation,
                reason="llm_call_failed",
            )

        try:
            return self._build_recommendation_from_llm_output(
                rca_report=input_data,
                output=llm_output,
                fallback_recommendation=deterministic_recommendation,
            )
        except SolutionRecommendationFallback as error:
            return self._with_fallback_metadata(
                deterministic_recommendation,
                reason=error.reason,
            )
        except Exception:
            return self._with_fallback_metadata(
                deterministic_recommendation,
                reason="llm_call_failed",
            )

    def _build_deterministic_recommendation(
        self,
        input_data: RCAReport,
    ) -> SolutionRecommendation:
        return SolutionRecommendation(
            recommendation_id=new_recommendation_id(),
            incident_id=input_data.incident_id,
            rca_report_id=input_data.report_id,
            summary=self._rules.build_summary(input_data),
            immediate_steps=self._rules.build_immediate_steps(input_data),
            long_term_steps=self._rules.build_long_term_steps(input_data),
            tests_to_add=self._rules.build_tests_to_add(input_data),
            monitoring_improvements=self._rules.build_monitoring_improvements(input_data),
            risk_notes=self._rules.build_risk_notes(input_data),
            confidence_score=input_data.confidence_score,
            evidence_ids=input_data.evidence_ids,
        )

    def _with_fallback_metadata(
        self,
        recommendation: SolutionRecommendation,
        *,
        reason: str,
    ) -> SolutionRecommendation:
        return recommendation.model_copy(
            update={
                "metadata": {
                    **recommendation.metadata,
                    "solution_writer": "deterministic_fallback",
                    "llm_output_validated": "false",
                    "fallback_used": "true",
                    "fallback_reason": reason,
                }
            }
        )

    def _build_recommendation_from_llm_output(
        self,
        *,
        rca_report: RCAReport,
        output: SolutionRecommendationOutput,
        fallback_recommendation: SolutionRecommendation,
    ) -> SolutionRecommendation:
        allowed_evidence_ids = set(fallback_recommendation.evidence_ids)
        invalid_evidence_ids = [
            evidence_id
            for evidence_id in output.evidence_ids
            if evidence_id not in allowed_evidence_ids
        ]

        if invalid_evidence_ids:
            raise SolutionRecommendationFallback("invalid_evidence_id")

        if output.confidence_score > rca_report.confidence_score:
            raise SolutionRecommendationFallback("llm_call_failed")

        if not output.immediate_steps:
            raise SolutionRecommendationFallback("missing_immediate_steps")

        if not output.tests_to_add:
            raise SolutionRecommendationFallback("missing_tests_to_add")

        if self._contains_forbidden_analyze_only_claim(output):
            raise SolutionRecommendationFallback("forbidden_completion_claim")

        if self._contains_evidence_id_in_prose(output):
            raise SolutionRecommendationFallback("invalid_evidence_id")

        if self._contains_unbalanced_inline_code(output):
            raise SolutionRecommendationFallback("unbalanced_inline_backticks")

        return SolutionRecommendation(
            recommendation_id=new_recommendation_id(),
            incident_id=rca_report.incident_id,
            rca_report_id=rca_report.report_id,
            summary=output.summary,
            immediate_steps=output.immediate_steps,
            long_term_steps=output.long_term_steps,
            tests_to_add=output.tests_to_add,
            monitoring_improvements=output.monitoring_improvements,
            risk_notes=output.risk_notes,
            confidence_score=output.confidence_score,
            evidence_ids=self._merge_evidence_ids(
                output.evidence_ids,
                fallback_recommendation.evidence_ids,
            ),
            metadata={
                **fallback_recommendation.metadata,
                "solution_writer": "llm",
                "llm_output_validated": "true",
                "fallback_used": "false",
            },
        )

    def _contains_forbidden_analyze_only_claim(
        self,
        output: SolutionRecommendationOutput,
    ) -> bool:
        values = [
            output.summary,
            *output.immediate_steps,
            *output.long_term_steps,
            *output.tests_to_add,
            *output.monitoring_improvements,
            *output.risk_notes,
        ]
        combined_text = "\n".join(values).lower()
        return any(phrase in combined_text for phrase in ANALYZE_ONLY_FORBIDDEN_PHRASES)

    def _contains_evidence_id_in_prose(
        self,
        output: SolutionRecommendationOutput,
    ) -> bool:
        return any(
            EVIDENCE_ID_IN_PROSE_PATTERN.search(value)
            for value in self._output_text_values(output)
        )

    def _merge_evidence_ids(
        self,
        preferred_ids: list[str],
        required_ids: list[str],
    ) -> list[str]:
        merged_ids: list[str] = []
        for evidence_id in [*preferred_ids, *required_ids]:
            if evidence_id not in merged_ids:
                merged_ids.append(evidence_id)
        return merged_ids

    def _contains_unbalanced_inline_code(
        self,
        output: SolutionRecommendationOutput,
    ) -> bool:
        return any(value.count("`") % 2 == 1 for value in self._output_text_values(output))

    def _output_text_values(self, output: SolutionRecommendationOutput) -> list[str]:
        return [
            output.summary,
            *output.immediate_steps,
            *output.long_term_steps,
            *output.tests_to_add,
            *output.monitoring_improvements,
            *output.risk_notes,
        ]

    def _build_system_prompt(self) -> str:
        return (
            "You write analyze-only production fix recommendations from RCA reports. "
            "Do not claim a fix has been applied. Do not invent evidence, files, "
            "owners, timelines, or implementation details. Reference only evidence "
            "IDs from the RCA."
        )

    def _build_prompt(
        self,
        rca_report: RCAReport,
        deterministic_recommendation: SolutionRecommendation,
    ) -> str:
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

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- None"
        return "\n".join(f"- {value}" for value in values)
