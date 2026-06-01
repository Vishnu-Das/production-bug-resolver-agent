"""Analyze-only patch diff generator agent."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.llm import LLMClient
from bug_resolver.prompts import PatchGenerationPromptBuilder
from bug_resolver.providers.patches import PatchContextProvider
from bug_resolver.rules import PatchEvidenceAuthorizationRules, PatchGenerationRules
from bug_resolver.schemas import (
    EvidenceItem,
    PatchGenerationResult,
    RCAReport,
    SolutionRecommendation,
)
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.utils.observability import get_logger


logger = get_logger(__name__)


class PatchGeneratorInput(StrictBaseModel):
    """Input bundle for safe unified diff suggestion generation."""

    rca_report: RCAReport
    solution_recommendation: SolutionRecommendation
    affected_files: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class PatchGeneratorAgent(BaseAgent[PatchGeneratorInput, PatchGenerationResult]):
    """Generate human-reviewable diffs without modifying the target repository."""

    name = "patch_generator_agent"

    def __init__(
        self,
        *,
        patch_context_provider: PatchContextProvider,
        llm_client: LLMClient | None = None,
        prompt_builder: PatchGenerationPromptBuilder | None = None,
        rules: PatchGenerationRules | None = None,
        evidence_authorization_rules: PatchEvidenceAuthorizationRules | None = None,
    ) -> None:
        self._patch_context_provider = patch_context_provider
        self._llm_client = llm_client
        self._prompt_builder = prompt_builder or PatchGenerationPromptBuilder()
        self._rules = rules or PatchGenerationRules()
        self._evidence_authorization_rules = (
            evidence_authorization_rules or PatchEvidenceAuthorizationRules()
        )

    async def _run(self, input_data: PatchGeneratorInput) -> PatchGenerationResult:
        authorized_files = self._code_backed_patch_targets(input_data)
        logger.info(
            "patch generator authorized files affected=%s authorized=%s evidence_ids=%s",
            input_data.affected_files,
            authorized_files,
            input_data.evidence_ids,
        )
        readable_files = await self._read_affected_files(authorized_files)
        if not readable_files:
            logger.warning("patch generation skipped no readable authorized files")
            return PatchGenerationResult(
                generated_diff=False,
                warnings=[
                    "Patch generation skipped because no safe code-backed affected files "
                    "were available."
                ],
                open_questions=[
                    "Which source file owns the implementation change for this incident?"
                ],
            )

        if self._llm_client is None:
            logger.warning("patch generation skipped no llm client")
            return PatchGenerationResult(
                generated_diff=False,
                warnings=[
                    "Patch generation skipped because no LLM client was configured."
                ],
            )

        prompt = self._prompt_builder.build_user_prompt(
            rca_report=input_data.rca_report,
            solution_recommendation=input_data.solution_recommendation,
            affected_files=authorized_files,
            evidence_ids=input_data.evidence_ids,
            file_contents=readable_files,
        )
        try:
            result = await self._llm_client.generate_structured(
                prompt,
                PatchGenerationResult,
                system_prompt=self._prompt_builder.build_system_prompt(),
            )
        except Exception:
            logger.exception("patch generation skipped llm failure")
            return PatchGenerationResult(
                generated_diff=False,
                warnings=[
                    "Patch generation skipped because the LLM provider failed."
                ],
                open_questions=[
                    "Should a developer prepare the diff manually from the patch plan?"
                ],
            )
        allowed_files = self._rules.allowed_patch_files(
            affected_files=authorized_files,
            readable_files=readable_files,
        )
        validated_result = self._rules.validate_patch_result(
            result=result,
            allowed_files=allowed_files,
            incident_context=self._incident_context(input_data),
        )
        logger.info(
            "patch generation validated generated_diff=%s file_patches=%s test_patches=%s warnings=%s",
            validated_result.generated_diff,
            len(validated_result.file_patches),
            len(validated_result.test_patches),
            validated_result.warnings,
        )
        return validated_result

    def _code_backed_patch_targets(self, input_data: PatchGeneratorInput) -> list[str]:
        code_evidence_paths = {
            *self._evidence_authorization_rules.direct_source_paths(
                input_data.evidence_items
            ),
            *self._source_paths_from_code_evidence(input_data.evidence_ids),
        }
        affected_files = {
            self._normalize_path(file_path) for file_path in input_data.affected_files
        }

        return sorted(code_evidence_paths & affected_files)

    def _source_paths_from_code_evidence(self, evidence_ids: list[str]) -> set[str]:
        paths: set[str] = set()
        for evidence_id in evidence_ids:
            normalized = evidence_id.replace("\\", "/")
            if not normalized.startswith("evidence-"):
                continue

            value = normalized.removeprefix("evidence-")
            if not value.startswith(("src/", "app/", "services/", "lib/")):
                continue

            file_path = value.split(":", maxsplit=1)[0]
            if file_path.endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
                paths.add(self._normalize_path(file_path))

        return paths

    async def _read_affected_files(self, affected_files: list[str]) -> dict[str, str]:
        readable_files: dict[str, str] = {}
        for file_path in affected_files:
            normalized_path = self._normalize_path(file_path)
            if not normalized_path:
                continue

            file_text = await self._patch_context_provider.read_file(normalized_path)
            if file_text is None:
                continue

            readable_files[normalized_path] = file_text
        return readable_files

    def _incident_context(self, input_data: PatchGeneratorInput) -> str:
        rca_report = input_data.rca_report
        solution = input_data.solution_recommendation
        return "\n".join(
            [
                rca_report.title,
                rca_report.incident_summary,
                rca_report.root_cause,
                rca_report.technical_explanation,
                rca_report.immediate_fix or "",
                solution.summary,
                *solution.immediate_steps,
            ]
        )

    def _normalize_path(self, file_path: str) -> str:
        return file_path.replace("\\", "/").strip().removeprefix("./")
