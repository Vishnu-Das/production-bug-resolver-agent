"""Prompt helper for RCA generation experiments."""

from __future__ import annotations

import json

from bug_resolver.schemas import EvidenceItem, RCAReport, WorkflowState
from bug_resolver.utils.paths import to_repo_relative_display_path


class RCAPromptBuilder:
    """
    Standalone RCA prompt template for prompt experiments.

    The production RCAWriterAgent owns its runtime structured prompt directly;
    keep this helper for isolated prompt iteration and documentation.
    """

    def build_system_prompt(self) -> str:
        """Build the runtime RCA writer system prompt."""
        return (
            "You write evidence-backed production RCA reports.\n"
            "Use only the provided incident and evidence. Do not invent files, logs, "
            "metrics, or facts. Keep the report analyze-only: recommend fixes and "
            "tests, but do not claim code was changed.\n"
            "Use only the ranked evidence below for root-cause claims. Do not cite or "
            "rely on raw retrieval candidates.\n"
            "Every RCA claim must be backed by one or more ranked evidence items. If "
            "evidence is weak or missing, say so.\n"
            "Distinguish runtime symptoms from root cause.\n"
            "Treat knowledge base evidence as supporting expected behavior, not as "
            "proof of implementation behavior.\n"
            "Treat semantic-only evidence as weaker unless supported by exact, file, "
            "graph, or log evidence.\n"
            "Reference only evidence IDs from the provided list.\n"
            "Use evidence IDs only in the structured evidence_ids field.\n"
            "Do not write internal evidence IDs in prose fields such as findings, "
            "root cause, technical explanation, confidence reason, fixes, tests, "
            "or open questions.\n"
            "Internal evidence IDs look like evidence-src/..., evidence-tests/..., "
            "evidence-eval/..., or evidence-docs/.... Never use those in prose.\n"
            "For prose, use the provided Display path value instead.\n"
            "Hypotheses must be formatted exactly as 'H1: ...', 'H2: ...', etc.\n"
            "selected_hypothesis_id must be exactly one of those IDs, for example 'H1'.\n"
            "Do not set selected_hypothesis_id to null when hypotheses exist.\n"
            "Use repo-relative display paths in prose.\n"
            "Keep Markdown inline code balanced with matching backticks."
        )

    def build_user_prompt(
        self,
        state: WorkflowState,
        deterministic_report: RCAReport,
    ) -> str:
        """Build the runtime RCA writer user prompt from evidence and baseline RCA."""
        prompt_evidence = self._prompt_evidence_items(state, deterministic_report)
        evidence_blocks = [
            self._format_evidence_block(index, evidence)
            for index, evidence in enumerate(prompt_evidence, start=1)
        ]
        evidence_text = "\n\n---\n\n".join(evidence_blocks)
        collected_evidence_ids = ", ".join(
            evidence.evidence_id for evidence in prompt_evidence
        )
        evidence_evaluation = self._format_evidence_evaluation(state, prompt_evidence)

        return (
            "Write a structured RCA report from the evidence.\n\n"
            f"Incident ID: {state.incident.incident_id}\n"
            f"Title: {state.incident.title}\n"
            f"Description: {state.incident.description}\n"
            f"Severity: {state.incident.severity.value}\n"
            f"Affected service: {state.incident.affected_service or 'unknown'}\n"
            f"Affected area: {state.incident.affected_area or 'unknown'}\n\n"
            "Important evidence usage rules:\n"
            "- Use Evidence ID values only in the evidence_ids field.\n"
            "- Do not copy Evidence ID values into prose fields.\n"
            "- Use Display path values in prose when referring to files.\n"
            "- Never write internal evidence prefixes like evidence-src/ or evidence-tests/ in prose.\n"
            "- Use only the ranked evidence below for root-cause claims.\n"
            "- Do not cite or rely on raw retrieval candidates.\n"
            "- Every RCA claim must be backed by one or more ranked evidence items.\n"
            "- If evidence is weak or missing, say so.\n"
            "- Distinguish runtime symptoms from root cause.\n"
            "- Treat knowledge base evidence as supporting expected behavior, not as proof of implementation behavior.\n"
            "- Treat semantic-only evidence as weaker unless supported by exact, file, graph, or log evidence.\n\n"
            f"Allowed evidence IDs: {collected_evidence_ids}\n"
            f"Focused baseline evidence IDs: {', '.join(deterministic_report.evidence_ids)}\n\n"
            f"{evidence_evaluation}\n\n"
            "Ranked Evidence:\n"
            f"{evidence_text}\n\n"
            "Deterministic baseline RCA for grounding:\n"
            "Use this only for reasoning. Do not copy its paths or evidence IDs into prose "
            "if they violate the Display path rules.\n"
            f"Root cause: {deterministic_report.root_cause}\n"
            "Focused code findings baseline:\n"
            f"{self._format_baseline_list(deterministic_report.code_findings)}\n"
            "Focused graph findings baseline:\n"
            f"{self._format_baseline_list(deterministic_report.graph_findings)}\n"
            "Focused knowledge-base findings baseline:\n"
            f"{self._format_baseline_list(deterministic_report.knowledge_base_findings)}\n"
            "Focused historical RCA findings baseline:\n"
            f"{self._format_baseline_list(deterministic_report.historical_findings)}\n"
            f"Immediate fix: {deterministic_report.immediate_fix or 'not specified'}\n"
            f"Confidence: {deterministic_report.confidence_score} because "
            f"{deterministic_report.confidence_reason}\n\n"
            "Keep Code Findings, Graph Findings, Knowledge Base Findings, and "
            "Historical Findings focused "
            "on the strongest baseline items. Use Graph Findings for caller/callee, "
            "config-reader, import, ownership, or class/function relationship evidence. "
            "Use Historical Findings only as recurrence or prior-incident context; "
            "do not use historical RCA as proof of the current root cause. "
            "Prefer the focused baseline evidence IDs and do not list unrelated retrieved "
            "context.\n"
            "Return an RCA report with clear findings, hypotheses, root cause, "
            "technical explanation, evidence IDs, confidence, recommended fix, "
            "prevention, tests, and open questions."
        )

    def build_prompt(self) -> str:
        """Build the short experimental RCA prompt used outside runtime agents."""
        return (
            "Generate an evidence-backed root cause analysis. "
            "Distinguish symptoms from root cause, cite evidence IDs, "
            "avoid unsupported claims, include confidence reasoning, "
            "and list open questions when evidence is incomplete."
        )

    def _format_baseline_list(self, values: list[str]) -> str:
        if not values:
            return "- None"

        return "\n".join(f"- {value}" for value in values)

    def _prompt_evidence_items(
        self,
        state: WorkflowState,
        deterministic_report: RCAReport,
    ) -> list[EvidenceItem]:
        evidence_by_id = {
            evidence.evidence_id: evidence for evidence in state.evidence_items
        }
        selected_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in deterministic_report.evidence_ids
            if evidence_id in evidence_by_id
        ]
        return selected_evidence or state.evidence_items

    def _format_evidence_block(self, index: int, evidence: EvidenceItem) -> str:
        metadata = evidence.metadata
        source_type = metadata.get("retrieval_source_type", evidence.source_type.value)
        score = metadata.get("score")
        header = f"{index}. [{source_type}"
        if score:
            header += f" | score={score}"
        header += "]"

        location = to_repo_relative_display_path(evidence.file_path or evidence.source_name)
        if evidence.line_start and evidence.line_end:
            location = f"{location}:{evidence.line_start}-{evidence.line_end}"

        lines = [
            header,
            f"   Evidence ID: {evidence.evidence_id}",
            f"   Source type: {evidence.source_type.value}",
            f"   Display path: {location}",
        ]
        if metadata.get("retriever_name"):
            lines.append(f"   Retriever: {metadata['retriever_name']}")
        if metadata.get("rank"):
            lines.append(f"   Rank: {metadata['rank']}")
        symbol_name = metadata.get("symbol_name") or metadata.get("qualified_symbol")
        if symbol_name:
            lines.append(f"   Symbol: {symbol_name}")

        score_reasons = self._metadata_list(metadata.get("score_reasons"))
        if score_reasons:
            lines.append("   Why it matters:")
            lines.extend(f"   - {reason}" for reason in score_reasons)

        lines.extend(
            [
                "   Evidence:",
                self._indent(self._shorten(evidence.content, max_length=1600), "   "),
            ]
        )
        return "\n".join(lines)

    def _format_evidence_evaluation(
        self,
        state: WorkflowState,
        evidence_items: list[EvidenceItem],
    ) -> str:
        retrieval_sufficient = self._first_metadata_value(
            evidence_items,
            "retrieval_sufficient_for_rca",
        )
        retrieval_confidence = self._first_metadata_value(
            evidence_items,
            "retrieval_confidence",
        )
        state_evaluation = state.evidence_evaluation
        sufficient_for_rca = retrieval_sufficient or (
            str(state_evaluation.can_write_rca).lower()
            if state_evaluation is not None
            else "unknown"
        )
        confidence = retrieval_confidence or (
            str(state_evaluation.confidence_score)
            if state_evaluation is not None
            else "unknown"
        )
        missing_evidence = self._unique(
            [
                *(
                    state_evaluation.missing_evidence
                    if state_evaluation is not None
                    else []
                ),
                *self._metadata_values(evidence_items, "retrieval_missing_evidence"),
            ]
        )
        warnings = self._unique(
            [
                *self._metadata_values(evidence_items, "retrieval_evaluation_warnings"),
                *self._metadata_values(evidence_items, "retrieval_warnings"),
            ]
        )

        return "\n".join(
            [
                "Evidence Evaluation:",
                f"- sufficient_for_rca: {sufficient_for_rca}",
                f"- confidence: {confidence}",
                "- missing evidence:",
                *self._format_list(missing_evidence),
                "- warnings:",
                *self._format_list(warnings),
            ]
        )

    def _metadata_values(
        self,
        evidence_items: list[EvidenceItem],
        key: str,
    ) -> list[str]:
        return [
            value
            for evidence in evidence_items
            for value in self._metadata_list(evidence.metadata.get(key))
        ]

    def _first_metadata_value(
        self,
        evidence_items: list[EvidenceItem],
        key: str,
    ) -> str | None:
        return next(
            (
                value
                for evidence in evidence_items
                if (value := evidence.metadata.get(key))
            ),
            None,
        )

    def _metadata_list(self, value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(parsed_value, list):
            return [str(item) for item in parsed_value if str(item).strip()]
        return [str(parsed_value)]

    def _format_list(self, values: list[str]) -> list[str]:
        return [f"  - {value}" for value in values] or ["  - None"]

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value.strip()))

    def _shorten(self, value: str, *, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[: max_length - 3].rstrip() + "..."

    def _indent(self, value: str, prefix: str) -> str:
        return "\n".join(f"{prefix}{line}" for line in value.splitlines())
