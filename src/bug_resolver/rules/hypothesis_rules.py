from __future__ import annotations

from bug_resolver.schemas import (
    CodeContext,
    EvidenceItem,
    Incident,
    KnowledgeContext,
    LogAnalysisResult,
)
from bug_resolver.schemas.common import HypothesisStatus


class HypothesisRules:
    """
    Deterministic rules for creating evidence-backed RCA hypotheses.

    The agent coordinates.
    These rules decide how to derive hypotheses from logs, code context,
    and knowledge-base context.
    """

    def build_evidence_items(
        self,
        log_analysis: LogAnalysisResult,
        code_contexts: list[CodeContext],
        knowledge_contexts: list[KnowledgeContext],
    ) -> list[EvidenceItem]:
        evidence_items: list[EvidenceItem] = []

        evidence_items.extend(log_analysis.evidence_items)
        evidence_items.extend(context.to_evidence_item() for context in code_contexts)
        evidence_items.extend(context.to_evidence_item() for context in knowledge_contexts)

        return evidence_items

    def supporting_evidence_ids(
        self,
        evidence_items: list[EvidenceItem],
    ) -> list[str]:
        return self.unique([item.evidence_id for item in evidence_items])

    def confidence_score(
        self,
        log_analysis: LogAnalysisResult,
        code_contexts: list[CodeContext],
        knowledge_contexts: list[KnowledgeContext],
    ) -> float:
        score = 0.20

        if log_analysis.exception_type:
            score += 0.15

        if log_analysis.exception_message:
            score += 0.15

        if log_analysis.stack_trace:
            score += 0.20

        if code_contexts:
            score += 0.20

        if knowledge_contexts:
            score += 0.10

        return min(score, 0.95)

    def status_for_confidence(self, confidence_score: float) -> HypothesisStatus:
        if confidence_score >= 0.70:
            return HypothesisStatus.SUPPORTED

        return HypothesisStatus.PROPOSED

    def build_title(
        self,
        log_analysis: LogAnalysisResult,
    ) -> str:
        if log_analysis.exception_type:
            return f"{log_analysis.exception_type} likely caused the incident"

        return "Application behavior likely caused the incident"

    def build_description(
        self,
        incident: Incident,
        log_analysis: LogAnalysisResult,
        code_contexts: list[CodeContext],
        knowledge_contexts: list[KnowledgeContext],
    ) -> str:
        parts = [
            f"Incident '{incident.title}' was analyzed using log evidence",
        ]

        if code_contexts:
            parts.append("retrieved code context")

        if knowledge_contexts:
            parts.append("knowledge-base context")

        if log_analysis.exception_type and log_analysis.exception_message:
            parts.append(
                f"The logs show {log_analysis.exception_type}: "
                f"{log_analysis.exception_message}"
            )

        if log_analysis.likely_failure_point:
            parts.append(
                f"The likely failure point is {log_analysis.likely_failure_point}"
            )

        return ". ".join(parts) + "."

    def build_suspected_root_cause(
        self,
        log_analysis: LogAnalysisResult,
        code_contexts: list[CodeContext],
    ) -> str:
        if (
            log_analysis.exception_type
            and log_analysis.exception_message
            and log_analysis.likely_failure_point
        ):
            return (
                f"{log_analysis.exception_type} occurred because "
                f"{log_analysis.exception_message} at "
                f"{log_analysis.likely_failure_point}."
            )

        if log_analysis.exception_type and log_analysis.exception_message:
            return (
                f"{log_analysis.exception_type} occurred because "
                f"{log_analysis.exception_message}."
            )

        if code_contexts:
            top_context = code_contexts[0]
            location = top_context.file_path
            if top_context.function_name:
                location = f"{location}::{top_context.function_name}"

            return (
                "The issue is likely related to the retrieved implementation "
                f"context in {location}."
            )

        return (
            "The root cause cannot be determined confidently from the available "
            "evidence yet."
        )

    def build_assumptions(
        self,
        code_contexts: list[CodeContext],
        knowledge_contexts: list[KnowledgeContext],
    ) -> list[str]:
        assumptions: list[str] = []

        if code_contexts:
            assumptions.append(
                "Retrieved code context is assumed to be relevant to the runtime failure."
            )

        if knowledge_contexts:
            assumptions.append(
                "Retrieved knowledge-base context is assumed to describe expected behavior."
            )

        return assumptions

    def build_open_questions(
        self,
        log_analysis: LogAnalysisResult,
        code_contexts: list[CodeContext],
        knowledge_contexts: list[KnowledgeContext],
    ) -> list[str]:
        questions: list[str] = []

        if not log_analysis.exception_type:
            questions.append("What exact exception type caused the failure?")

        if not log_analysis.exception_message:
            questions.append("What exact exception message was emitted?")

        if not log_analysis.stack_trace:
            questions.append("Which source file and function produced the failure?")

        if not code_contexts:
            questions.append("Which implementation code path maps to the log failure?")

        if not knowledge_contexts:
            questions.append("What is the expected behavior according to project documentation?")

        return questions

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