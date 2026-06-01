"""RCA writer agent with LLM-first generation and deterministic fallback."""

from __future__ import annotations

import re

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.llm.base import LLMClient
from bug_resolver.prompts import RCAPromptBuilder
from bug_resolver.rules.rca_rules import RCARules
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas import EvidenceSourceType, RCAReport, WorkflowState
from bug_resolver.utils.ids import new_rca_report_id
from bug_resolver.utils.observability import get_logger


ANALYZE_ONLY_COMPLETION_CLAIM_PHRASES = (
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
INTERNAL_EVIDENCE_PREFIXES = (
    "evidence-src/",
    "evidence-src\\",
    "evidence-tests/",
    "evidence-tests\\",
    "evidence-eval/",
    "evidence-eval\\",
    "evidence-docs/",
    "evidence-docs\\",
)
LOG_FINDING_MARKERS = (
    "log evidence",
    "logged",
    "request_id=",
    "trace_id=",
    "user feedback",
    "warning ",
    " error ",
    " info ",
)
HYPOTHESIS_PREFIX_PATTERN = re.compile(r"^H\d+\s*:?\s*", re.IGNORECASE)
EVIDENCE_ID_IN_PROSE_PATTERN = re.compile(
    r"\b(?:EVID-[A-Z0-9_-]+|EVIDENCE-[A-Z0-9_-]+|kb-[A-Za-z0-9_-]+|"
    r"evidence-(?:src|tests|eval|docs)[/\\][A-Za-z0-9_./\\:-]+)\b",
)

logger = get_logger(__name__)


class RCAWriterFallback(Exception):
    """Internal control exception carrying the deterministic fallback reason."""

    def __init__(self, reason: str, *, details: dict[str, list[str]] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


class RCAWriterOutput(StrictBaseModel):
    """Structured LLM response expected from the RCA writer model."""

    title: str = Field(..., min_length=1)
    incident_summary: str = Field(..., min_length=1)
    impact: str | None = None
    symptoms: list[str]
    log_findings: list[str]
    code_findings: list[str]
    graph_findings: list[str] = Field(default_factory=list)
    knowledge_base_findings: list[str]
    historical_findings: list[str] = Field(default_factory=list)
    hypotheses_considered: list[str]
    selected_hypothesis_id: str | None = None
    root_cause: str = Field(..., min_length=1)
    technical_explanation: str = Field(..., min_length=1)
    evidence_ids: list[str]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_reason: str = Field(..., min_length=1)
    immediate_fix: str | None = None
    long_term_prevention: str | None = None
    tests_to_add: list[str]
    open_questions: list[str]
    low_confidence_warning: str | None = None


class RCAWriterAgent(BaseAgent[WorkflowState, RCAReport]):
    """Writes an evidence-backed RCA from dynamic investigation state."""

    name = "rca_writer_agent"

    def __init__(
        self,
        rules: RCARules | None = None,
        llm_client: LLMClient | None = None,
        prompt_builder: RCAPromptBuilder | None = None,
    ) -> None:
        self._rules = rules or RCARules()
        self._llm_client = llm_client
        self._prompt_builder = prompt_builder or RCAPromptBuilder()

    async def _run(self, input_data: WorkflowState) -> RCAReport:
        logger.info(
            "rca writer started incident_id=%s evidence_count=%s",
            input_data.incident.incident_id,
            len(input_data.evidence_items),
        )
        deterministic_report = self._build_deterministic_report(input_data)

        if self._llm_client is None:
            logger.info("rca writer using fallback reason=llm_client_not_configured")
            return self._with_fallback_metadata(
                deterministic_report,
                reason="llm_client_not_configured",
            )

        try:
            llm_output = await self._llm_client.generate_structured(
                self._build_prompt(input_data, deterministic_report),
                RCAWriterOutput,
                system_prompt=self._build_system_prompt(),
            )
        except Exception:
            logger.exception("rca writer llm call failed")
            return self._with_fallback_metadata(
                deterministic_report,
                reason="llm_call_failed",
            )

        try:
            report = self._build_report_from_llm_output(
                state=input_data,
                output=llm_output,
                fallback_report=deterministic_report,
            )
            logger.info(
                "rca writer accepted llm output report_id=%s evidence_count=%s",
                report.report_id,
                len(report.evidence_ids),
            )
            return report
        except RCAWriterFallback as error:
            logger.warning(
                "rca writer using fallback reason=%s details=%s",
                error.reason,
                error.details,
            )
            return self._with_fallback_metadata(
                deterministic_report,
                reason=error.reason,
            )
        except Exception:
            logger.exception("rca writer failed while validating llm output")
            return self._with_fallback_metadata(
                deterministic_report,
                reason="llm_call_failed",
            )

    def _build_deterministic_report(self, input_data: WorkflowState) -> RCAReport:
        return RCAReport(
            report_id=new_rca_report_id(),
            incident_id=input_data.incident.incident_id,
            title=self._rules.build_title(input_data),
            incident_summary=self._rules.build_incident_summary(input_data),
            impact=self._rules.build_impact(input_data),
            symptoms=self._rules.build_symptoms(input_data),
            log_findings=self._rules.build_log_findings(input_data),
            code_findings=self._rules.build_code_findings(input_data),
            graph_findings=self._rules.build_graph_findings(input_data),
            knowledge_base_findings=self._rules.build_knowledge_base_findings(input_data),
            historical_findings=self._rules.build_historical_findings(input_data),
            hypotheses_considered=self._rules.build_hypotheses_considered(input_data),
            selected_hypothesis_id=self._rules.selected_hypothesis_id(input_data),
            root_cause=self._rules.build_root_cause(input_data),
            technical_explanation=self._rules.build_technical_explanation(input_data),
            evidence_ids=self._rules.evidence_ids(input_data),
            confidence_score=self._rules.confidence_score(input_data),
            confidence_reason=self._rules.confidence_reason(input_data),
            immediate_fix=self._rules.immediate_fix(input_data),
            long_term_prevention=self._rules.long_term_prevention(),
            tests_to_add=self._rules.tests_to_add(input_data),
            open_questions=self._rules.open_questions(input_data),
            low_confidence_warning=self._rules.low_confidence_warning(input_data),
            metadata={
                "evidence_count": str(len(input_data.evidence_items)),
                "dynamic_workflow": "true",
            },
        )

    def _with_fallback_metadata(self, report: RCAReport, *, reason: str) -> RCAReport:
        return report.model_copy(
            update={
                "metadata": {
                    **report.metadata,
                    "rca_writer": "deterministic_fallback",
                    "llm_output_validated": "false",
                    "fallback_used": "true",
                    "fallback_reason": reason,
                }
            }
        )

    def _build_report_from_llm_output(
        self,
        *,
        state: WorkflowState,
        output: RCAWriterOutput,
        fallback_report: RCAReport,
    ) -> RCAReport:
        collected_evidence_ids = {evidence.evidence_id for evidence in state.evidence_items}
        selected_evidence_ids = set(fallback_report.evidence_ids)
        invalid_evidence_ids = [
            evidence_id
            for evidence_id in output.evidence_ids
            if evidence_id not in collected_evidence_ids
        ]
        if invalid_evidence_ids:
            raise RCAWriterFallback(
                "invalid_evidence_id",
                details={"invalid_ids": invalid_evidence_ids},
            )

        evidence_ids = [
            evidence_id
            for evidence_id in output.evidence_ids
            if evidence_id in collected_evidence_ids
        ]
        extra_collected_evidence_ids = [
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in selected_evidence_ids
        ]
        if extra_collected_evidence_ids:
            logger.info(
                "rca writer accepted collected evidence outside deterministic selection ids=%s",
                extra_collected_evidence_ids,
            )
        hypotheses_considered, selected_hypothesis_id = self._normalize_hypotheses(
            output.hypotheses_considered,
            output.selected_hypothesis_id,
        )
        if not evidence_ids:
            raise RCAWriterFallback(
                "invalid_evidence_id",
                details={"invalid_ids": output.evidence_ids},
            )

        if output.confidence_score < state.confidence_threshold and not output.open_questions:
            raise RCAWriterFallback("llm_call_failed")

        if output.confidence_score > fallback_report.confidence_score:
            raise RCAWriterFallback("llm_call_failed")

        if not hypotheses_considered:
            raise RCAWriterFallback("missing_hypotheses")

        if selected_hypothesis_id is None:
            raise RCAWriterFallback("missing_selected_hypothesis_id")

        if not any(
            hypothesis.startswith(f"{selected_hypothesis_id}:")
            for hypothesis in hypotheses_considered
        ):
            raise RCAWriterFallback("selected_hypothesis_id_not_found")

        if not output.tests_to_add:
            raise RCAWriterFallback("missing_tests_to_add")

        if self._contains_forbidden_analyze_only_claim(output):
            raise RCAWriterFallback("forbidden_completion_claim")

        if self._contains_internal_evidence_path(output):
            raise RCAWriterFallback(
                "internal_evidence_prefix_in_prose",
                details={
                    "matches": self._internal_evidence_path_matches(output),
                },
            )

        if self._contains_evidence_id_in_prose(output):
            raise RCAWriterFallback(
                "invalid_evidence_id",
                details={"matches": self._evidence_id_prose_matches(output)},
            )

        if self._has_misclassified_findings(output):
            raise RCAWriterFallback("llm_call_failed")

        if self._contains_unbalanced_inline_code(output):
            raise RCAWriterFallback("unbalanced_inline_backticks")

        evidence_ids = self._ensure_source_evidence_when_findings_exist(
            state=state,
            findings=output.code_findings,
            source_type=EvidenceSourceType.CODE,
            evidence_ids=evidence_ids,
            fallback_report=fallback_report,
        )
        if output.code_findings:
            evidence_ids = self._rules.ensure_direct_source_evidence_ids(
                state,
                evidence_ids,
            )
        evidence_ids = self._ensure_source_evidence_when_findings_exist(
            state=state,
            findings=output.graph_findings,
            source_type=EvidenceSourceType.GRAPH,
            evidence_ids=evidence_ids,
            fallback_report=fallback_report,
        )
        evidence_ids = self._ensure_source_evidence_when_findings_exist(
            state=state,
            findings=output.historical_findings,
            source_type=EvidenceSourceType.HISTORICAL_RCA,
            evidence_ids=evidence_ids,
            fallback_report=fallback_report,
        )

        return RCAReport(
            report_id=new_rca_report_id(),
            incident_id=state.incident.incident_id,
            title=output.title,
            incident_summary=output.incident_summary,
            impact=output.impact,
            symptoms=output.symptoms,
            log_findings=output.log_findings,
            code_findings=output.code_findings,
            graph_findings=output.graph_findings,
            knowledge_base_findings=output.knowledge_base_findings,
            historical_findings=output.historical_findings,
            hypotheses_considered=hypotheses_considered,
            selected_hypothesis_id=selected_hypothesis_id,
            root_cause=output.root_cause,
            technical_explanation=output.technical_explanation,
            evidence_ids=evidence_ids,
            confidence_score=output.confidence_score,
            confidence_reason=output.confidence_reason,
            immediate_fix=output.immediate_fix,
            long_term_prevention=output.long_term_prevention,
            tests_to_add=output.tests_to_add,
            open_questions=output.open_questions,
            low_confidence_warning=output.low_confidence_warning,
            metadata={
                **fallback_report.metadata,
                "rca_writer": "llm",
                "llm_output_validated": "true",
                "fallback_used": "false",
            },
        )

    def _ensure_source_evidence_when_findings_exist(
        self,
        *,
        state: WorkflowState,
        findings: list[str],
        source_type: EvidenceSourceType,
        evidence_ids: list[str],
        fallback_report: RCAReport,
    ) -> list[str]:
        if not findings:
            return evidence_ids

        source_evidence_ids = {
            evidence.evidence_id
            for evidence in state.evidence_items
            if evidence.source_type == source_type
        }
        if not source_evidence_ids:
            return evidence_ids

        if any(evidence_id in source_evidence_ids for evidence_id in evidence_ids):
            return evidence_ids

        selected_source_evidence_ids = [
            evidence_id
            for evidence_id in fallback_report.evidence_ids
            if evidence_id in source_evidence_ids
        ]
        if not selected_source_evidence_ids:
            return evidence_ids

        return self._merge_evidence_ids(evidence_ids, selected_source_evidence_ids)

    def _merge_evidence_ids(self, *groups: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()

        for group in groups:
            for evidence_id in group:
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                merged.append(evidence_id)

        return merged

    def _contains_forbidden_analyze_only_claim(self, output: RCAWriterOutput) -> bool:
        values = [
            output.title,
            output.incident_summary,
            output.impact or "",
            *output.symptoms,
            *output.log_findings,
            *output.code_findings,
            *output.graph_findings,
            *output.knowledge_base_findings,
            *output.historical_findings,
            *output.hypotheses_considered,
            output.root_cause,
            output.technical_explanation,
            output.confidence_reason,
            output.immediate_fix or "",
            output.long_term_prevention or "",
            *output.tests_to_add,
            *output.open_questions,
            output.low_confidence_warning or "",
        ]
        combined_text = "\n".join(values).lower()
        return any(
            phrase in combined_text for phrase in ANALYZE_ONLY_COMPLETION_CLAIM_PHRASES
        )

    def _contains_internal_evidence_path(self, output: RCAWriterOutput) -> bool:
        return bool(self._internal_evidence_path_matches(output))

    def _internal_evidence_path_matches(self, output: RCAWriterOutput) -> list[str]:
        matches: list[str] = []
        for value in self._output_text_values(output):
            normalized_value = value.lower()
            if any(prefix in normalized_value for prefix in INTERNAL_EVIDENCE_PREFIXES):
                matches.append(value)
        return matches[:5]

    def _contains_evidence_id_in_prose(self, output: RCAWriterOutput) -> bool:
        return bool(self._evidence_id_prose_matches(output))

    def _evidence_id_prose_matches(self, output: RCAWriterOutput) -> list[str]:
        matches: list[str] = []
        for value in self._output_text_values(output):
            match = EVIDENCE_ID_IN_PROSE_PATTERN.search(value)
            if match is not None:
                matches.append(match.group(0))
        return matches[:10]

    def _has_misclassified_findings(self, output: RCAWriterOutput) -> bool:
        return any(self._looks_like_log_finding(finding) for finding in output.code_findings)

    def _looks_like_log_finding(self, value: str) -> bool:
        normalized = value.lower()
        return any(marker in normalized for marker in LOG_FINDING_MARKERS)

    def _contains_unbalanced_inline_code(self, output: RCAWriterOutput) -> bool:
        return any(value.count("`") % 2 == 1 for value in self._output_text_values(output))

    def _output_text_values(self, output: RCAWriterOutput) -> list[str]:
        return [
            output.title,
            output.incident_summary,
            output.impact or "",
            *output.symptoms,
            *output.log_findings,
            *output.code_findings,
            *output.graph_findings,
            *output.knowledge_base_findings,
            *output.historical_findings,
            *output.hypotheses_considered,
            output.root_cause,
            output.technical_explanation,
            output.confidence_reason,
            output.immediate_fix or "",
            output.long_term_prevention or "",
            *output.tests_to_add,
            *output.open_questions,
            output.low_confidence_warning or "",
        ]

    def _build_system_prompt(self) -> str:
        return self._prompt_builder.build_system_prompt()

    def _build_prompt(
        self,
        state: WorkflowState,
        deterministic_report: RCAReport,
    ) -> str:
        return self._prompt_builder.build_user_prompt(state, deterministic_report)

    def _validate_input(self, input_data: WorkflowState) -> None:
        super()._validate_input(input_data)

        if not input_data.evidence_items:
            raise ValueError(f"{self.name} requires evidence before writing an RCA.")

        if input_data.evidence_evaluation is None:
            raise ValueError(f"{self.name} requires evidence evaluation before RCA.")

    def _normalize_hypotheses(
        self,
        hypotheses: list[str],
        selected_hypothesis_id: str | None,
    ) -> tuple[list[str], str | None]:
        cleaned_hypotheses = [
            hypothesis.strip() for hypothesis in hypotheses if hypothesis and hypothesis.strip()
        ]

        normalized_hypotheses: list[str] = []

        for index, hypothesis in enumerate(cleaned_hypotheses, start=1):
            hypothesis_id = f"H{index}"

            if hypothesis.startswith(f"{hypothesis_id}:"):
                normalized_hypotheses.append(hypothesis)
                continue

            # If the LLM already used a different H-number prefix, remove it and
            # rewrite based on actual list order.
            if len(hypothesis) > 3 and hypothesis[0].upper() == "H" and hypothesis[1].isdigit():
                _, _, remainder = hypothesis.partition(":")
                hypothesis = HYPOTHESIS_PREFIX_PATTERN.sub("", hypothesis).strip() or hypothesis

            normalized_hypotheses.append(f"{hypothesis_id}: {hypothesis}")

        normalized_selected_id = self._normalize_selected_hypothesis_id(
            selected_hypothesis_id=selected_hypothesis_id,
            hypothesis_count=len(normalized_hypotheses),
        )

        if normalized_selected_id is None and normalized_hypotheses:
            normalized_selected_id = "H1"

        return normalized_hypotheses, normalized_selected_id

    def _normalize_selected_hypothesis_id(
        self,
        *,
        selected_hypothesis_id: str | None,
        hypothesis_count: int,
    ) -> str | None:
        if not selected_hypothesis_id:
            return None

        normalized = selected_hypothesis_id.strip().upper().rstrip(":")

        if normalized.isdigit():
            normalized = f"H{normalized}"

        if len(normalized) >= 2 and normalized[0] == "H" and normalized[1:].isdigit():
            hypothesis_number = int(normalized[1:])
            if 1 <= hypothesis_number <= hypothesis_count:
                return normalized

        return normalized
