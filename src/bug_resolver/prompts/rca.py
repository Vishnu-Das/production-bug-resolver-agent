"""Prompt helper for RCA generation experiments."""

from __future__ import annotations

from bug_resolver.schemas import RCAReport, WorkflowState
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
        evidence_blocks: list[str] = []

        for evidence in state.evidence_items:
            location = to_repo_relative_display_path(evidence.file_path or evidence.source_name)
            if evidence.line_start and evidence.line_end:
                location = f"{location}:{evidence.line_start}-{evidence.line_end}"

            evidence_blocks.append(
                "\n".join(
                    [
                        f"Evidence ID: {evidence.evidence_id}",
                        f"Source type: {evidence.source_type.value}",
                        f"Display path: {location}",
                        f"Content: {evidence.content}",
                    ]
                )
            )

        evidence_text = "\n\n---\n\n".join(evidence_blocks)
        collected_evidence_ids = ", ".join(
            evidence.evidence_id for evidence in state.evidence_items
        )

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
            "- Never write internal evidence prefixes like evidence-src/ or evidence-tests/ in prose.\n\n"
            f"Allowed evidence IDs: {collected_evidence_ids}\n"
            f"Focused baseline evidence IDs: {', '.join(deterministic_report.evidence_ids)}\n\n"
            "Evidence blocks:\n"
            f"{evidence_text}\n\n"
            "Deterministic baseline RCA for grounding:\n"
            "Use this only for reasoning. Do not copy its paths or evidence IDs into prose "
            "if they violate the Display path rules.\n"
            f"Root cause: {deterministic_report.root_cause}\n"
            f"Technical explanation: {deterministic_report.technical_explanation}\n"
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
