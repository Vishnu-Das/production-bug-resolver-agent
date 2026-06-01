"""Analyze-only patch suggestion agent."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.llm.base import LLMClient
from bug_resolver.rules.patch_suggestion_rules import PatchSuggestionRules
from bug_resolver.schemas import (
    EvidenceItem,
    PatchSuggestion,
    RCAReport,
    SolutionRecommendation,
)
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.utils.observability import get_logger


PATCH_SUGGESTION_FORBIDDEN_PHRASES = (
    "i fixed",
    "we fixed",
    "has been fixed",
    "was fixed",
    "is fixed",
    "deployed",
    "committed",
    "created a pull request",
    "opened a pull request",
)
logger = get_logger(__name__)


class PatchSuggestionInput(StrictBaseModel):
    """Input bundle for generating a patch suggestion."""

    rca_report: RCAReport
    solution_recommendation: SolutionRecommendation
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class PatchSuggestionNarrativeOutput(StrictBaseModel):
    """LLM-written narrative fields for a deterministic patch plan."""

    summary: str = Field(..., min_length=1)
    behavior_changes: list[str]
    tests_to_add: list[str]
    risk_notes: list[str]
    open_questions: list[str]
    warnings: list[str] = Field(default_factory=list)


class PatchSuggestionAgent(BaseAgent[PatchSuggestionInput, PatchSuggestion]):
    """Builds a human-reviewable patch plan without changing code."""

    name = "patch_suggestion_agent"

    def __init__(
        self,
        rules: PatchSuggestionRules | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._rules = rules or PatchSuggestionRules()
        self._llm_client = llm_client

    async def _run(self, input_data: PatchSuggestionInput) -> PatchSuggestion:
        suggestion = self._rules.build_patch_suggestion(
            rca_report=input_data.rca_report,
            solution=input_data.solution_recommendation,
            evidence_items=input_data.evidence_items,
        )
        suggestion = await self._maybe_apply_llm_narrative(
            input_data=input_data,
            suggestion=suggestion,
        )
        logger.info(
            "patch suggestion generated incident_id=%s affected_files=%s evidence_count=%s",
            suggestion.incident_id,
            suggestion.affected_files,
            len(suggestion.evidence_ids),
        )
        return suggestion

    async def _maybe_apply_llm_narrative(
        self,
        *,
        input_data: PatchSuggestionInput,
        suggestion: PatchSuggestion,
    ) -> PatchSuggestion:
        if self._llm_client is None:
            return suggestion

        try:
            output = await self._llm_client.generate_structured(
                self._build_prompt(
                    input_data=input_data,
                    deterministic_suggestion=suggestion,
                ),
                PatchSuggestionNarrativeOutput,
                system_prompt=self._build_system_prompt(),
            )
        except Exception:
            logger.exception("patch suggestion llm call failed")
            return suggestion.model_copy(
                update={
                    "metadata": {
                        **suggestion.metadata,
                        "patch_suggestion_writer": "deterministic_fallback",
                        "llm_output_validated": "false",
                        "fallback_used": "true",
                        "fallback_reason": "llm_call_failed",
                    }
                }
            )

        if self._contains_forbidden_analyze_only_claim(output):
            logger.warning("patch suggestion llm output rejected reason=forbidden_claim")
            return suggestion.model_copy(
                update={
                    "metadata": {
                        **suggestion.metadata,
                        "patch_suggestion_writer": "deterministic_fallback",
                        "llm_output_validated": "false",
                        "fallback_used": "true",
                        "fallback_reason": "forbidden_completion_claim",
                    }
                }
            )

        return suggestion.model_copy(
            update={
                "summary": output.summary,
                "behavior_changes": self._unique_or_fallback(
                    output.behavior_changes,
                    suggestion.behavior_changes,
                ),
                "tests_to_add": self._unique_or_fallback(
                    output.tests_to_add,
                    suggestion.tests_to_add,
                ),
                "risk_notes": self._unique_or_fallback(
                    output.risk_notes,
                    suggestion.risk_notes,
                ),
                "open_questions": self._unique_or_fallback(
                    output.open_questions,
                    suggestion.open_questions,
                ),
                "warnings": self._unique([*suggestion.warnings, *output.warnings]),
                "metadata": {
                    **suggestion.metadata,
                    "patch_suggestion_writer": "hybrid_llm",
                    "llm_output_validated": "true",
                    "fallback_used": "false",
                },
            }
        )

    def _contains_forbidden_analyze_only_claim(
        self,
        output: PatchSuggestionNarrativeOutput,
    ) -> bool:
        combined_text = "\n".join(
            [
                output.summary,
                *output.behavior_changes,
                *output.tests_to_add,
                *output.risk_notes,
                *output.open_questions,
                *output.warnings,
            ]
        ).lower()
        return any(phrase in combined_text for phrase in PATCH_SUGGESTION_FORBIDDEN_PHRASES)

    def _build_system_prompt(self) -> str:
        return (
            "You write concise analyze-only patch plan narrative. "
            "Do not claim code was changed, committed, deployed, or fixed. "
            "Do not add affected files, patches, evidence IDs, or validation commands. "
            "Use the deterministic file authorization exactly as provided."
        )

    def _build_prompt(
        self,
        *,
        input_data: PatchSuggestionInput,
        deterministic_suggestion: PatchSuggestion,
    ) -> str:
        return "\n".join(
            [
                "Rewrite only the narrative fields for this analyze-only patch plan.",
                "",
                f"Incident ID: {deterministic_suggestion.incident_id}",
                f"RCA root cause: {input_data.rca_report.root_cause}",
                f"Immediate fix: {input_data.rca_report.immediate_fix or ''}",
                f"Solution summary: {input_data.solution_recommendation.summary}",
                "",
                "Patchable owner files:",
                *[
                    f"- {file_path}"
                    for file_path in deterministic_suggestion.affected_files
                ],
                "",
                "Supporting context files:",
                *[
                    f"- {file_path.strip()}"
                    for file_path in deterministic_suggestion.metadata.get(
                        "supporting_context_files",
                        "",
                    ).split(",")
                    if file_path.strip()
                ],
                "",
                "Existing deterministic behavior changes:",
                *[
                    f"- {change}"
                    for change in deterministic_suggestion.behavior_changes
                ],
                "",
                "Existing tests to add:",
                *[
                    f"- {test}"
                    for test in deterministic_suggestion.tests_to_add
                ],
                "",
                "Existing risk notes:",
                *[
                    f"- {risk}"
                    for risk in deterministic_suggestion.risk_notes
                ],
                "",
                "Existing open questions:",
                *[
                    f"- {question}"
                    for question in deterministic_suggestion.open_questions
                ],
            ]
        )

    def _unique_or_fallback(
        self,
        values: list[str],
        fallback_values: list[str],
    ) -> list[str]:
        unique_values = self._unique(values)
        return unique_values or fallback_values

    def _unique(self, values: list[str]) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_values.append(normalized)
        return unique_values
