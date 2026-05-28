"""Prompt builder for analyze-only unified diff generation."""

from __future__ import annotations

from bug_resolver.schemas import RCAReport, SolutionRecommendation


class PatchGenerationPromptBuilder:
    """Build prompts for safe, human-reviewable patch diff suggestions."""

    def build_system_prompt(self) -> str:
        """Build the patch generation system prompt."""
        return (
            "You generate human-reviewable unified diffs for production bug fixes. "
            "Do not apply patches. Do not claim code has changed. Do not invent files. "
            "Prefer standard unified diffs with --- a/path and +++ b/path headers. "
            "apply_patch-style update blocks are acceptable only when they update the "
            "same readable affected file. "
            "Only modify files whose exact contents are provided. If code context is "
            "insufficient, return open questions or warnings instead of fake diffs. "
            "Historical RCA and knowledge-base evidence are supporting context only; "
            "current code evidence is primary. Return structured output matching "
            "PatchGenerationResult."
        )

    def build_user_prompt(
        self,
        *,
        rca_report: RCAReport,
        solution_recommendation: SolutionRecommendation,
        affected_files: list[str],
        evidence_ids: list[str],
        file_contents: dict[str, str],
    ) -> str:
        """Build the patch generation user prompt from exact file contents."""
        return (
            "Generate analyze-only unified diff suggestions.\n\n"
            f"Incident ID: {rca_report.incident_id}\n"
            f"RCA root cause: {rca_report.root_cause}\n"
            f"Immediate fix: {rca_report.immediate_fix or 'not specified'}\n"
            "Solution steps:\n"
            f"{self._format_list(solution_recommendation.immediate_steps)}\n"
            "Affected files:\n"
            f"{self._format_list(affected_files)}\n"
            "Selected evidence IDs:\n"
            f"{self._format_list(evidence_ids)}\n\n"
            "Exact readable target file contents:\n"
            f"{self._format_file_contents(file_contents)}\n\n"
            "Return patches only for readable affected files listed above. "
            "Prefer standard unified diff format with headers for the same file path, "
            "for example --- a/src/file.py and +++ b/src/file.py. If you return "
            "apply_patch syntax, use only *** Update File for one readable affected "
            "file; do not use add, delete, or move patch operations."
        )

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- None"

        return "\n".join(f"- {value}" for value in values)

    def _format_file_contents(self, file_contents: dict[str, str]) -> str:
        if not file_contents:
            return "- None"

        blocks: list[str] = []
        for file_path, content in file_contents.items():
            blocks.append(
                "\n".join(
                    [
                        f"File: {file_path}",
                        "```text",
                        content,
                        "```",
                    ]
                )
            )
        return "\n\n".join(blocks)
