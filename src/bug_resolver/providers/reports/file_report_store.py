"""File-backed report store for JSON and Markdown RCA artifacts."""

import json
from pathlib import Path

from bug_resolver.providers.reports.base import ReportStore
from bug_resolver.schemas.patch_suggestion import FilePatch, PatchSuggestion
from bug_resolver.schemas.rca import RCAReport
from bug_resolver.schemas.solution import SolutionRecommendation


class FileReportStore(ReportStore):
    """Persist RCA and solution reports as JSON and Markdown files."""

    def __init__(self, reports_dir: str | Path) -> None:
        self.reports_dir = Path(reports_dir)

    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
        patch_suggestion: PatchSuggestion | None = None,
    ) -> list[Path]:
        report_dir = self.reports_dir / "incidents" / report.incident_id
        report_dir.mkdir(parents=True, exist_ok=True)

        json_path = report_dir / "rca.json"
        markdown_path = report_dir / "rca.md"

        self._save_json(report=report, json_path=json_path)
        self._save_markdown(report=report, markdown_path=markdown_path)

        written_paths = [markdown_path, json_path]

        if solution is not None:
            solution_path = report_dir / "solution.json"
            solution_markdown_path = report_dir / "solution.md"
            self._save_solution_json(solution=solution, json_path=solution_path)
            self._save_solution_markdown(
                solution=solution,
                markdown_path=solution_markdown_path,
            )
            written_paths.extend([solution_path, solution_markdown_path])

        if patch_suggestion is not None:
            patch_path = report_dir / "patch.json"
            patch_markdown_path = report_dir / "patch.md"
            self._save_patch_json(patch_suggestion=patch_suggestion, json_path=patch_path)
            self._save_patch_markdown(
                patch_suggestion=patch_suggestion,
                markdown_path=patch_markdown_path,
            )
            written_paths.extend([patch_path, patch_markdown_path])

        return written_paths

    async def get_report(self, incident_id: str) -> RCAReport | None:
        json_path = self.reports_dir / "incidents" / incident_id / "rca.json"
        if not json_path.exists():
            return None
        return RCAReport.model_validate_json(json_path.read_text(encoding="utf-8"))

    def _save_json(self, report: RCAReport, json_path: Path) -> None:
        json_path.write_text(
            json.dumps(
                report.model_dump(mode="json"),
                indent=2,
            ),
            encoding="utf-8",
        )

    def _save_solution_json(
        self,
        solution: SolutionRecommendation,
        json_path: Path,
    ) -> None:
        json_path.write_text(
            json.dumps(
                solution.model_dump(mode="json"),
                indent=2,
            ),
            encoding="utf-8",
        )

    def _save_patch_json(
        self,
        patch_suggestion: PatchSuggestion,
        json_path: Path,
    ) -> None:
        json_path.write_text(
            json.dumps(
                patch_suggestion.model_dump(mode="json"),
                indent=2,
            ),
            encoding="utf-8",
        )

    def _save_patch_markdown(
        self,
        patch_suggestion: PatchSuggestion,
        markdown_path: Path,
    ) -> None:
        markdown_path.write_text(
            self._build_patch_markdown(patch_suggestion),
            encoding="utf-8",
        )

    def _save_solution_markdown(
        self,
        solution: SolutionRecommendation,
        markdown_path: Path,
    ) -> None:
        markdown_path.write_text(
            self._build_solution_markdown(solution),
            encoding="utf-8",
        )

    def _save_markdown(self, report: RCAReport, markdown_path: Path) -> None:
        markdown_path.write_text(
            self._build_markdown(report),
            encoding="utf-8",
        )

    def _build_markdown(self, report: RCAReport) -> str:
        lines: list[str] = [f"# {report.title}"]
        self._add_section(lines, "## Incident Summary", [report.incident_summary])
        self._add_section(lines, "## Impact", [report.impact or "Not specified"])
        self._add_section(lines, "## Symptoms", self._render_list_lines(report.symptoms))
        self._add_section(
            lines,
            "## Log Findings",
            self._render_list_lines(report.log_findings),
        )
        self._add_section(
            lines,
            "## Code Findings",
            self._render_list_lines(report.code_findings),
        )
        self._add_section(
            lines,
            "## Graph Findings",
            self._render_list_lines(report.graph_findings),
        )
        self._add_section(
            lines,
            "## Knowledge Base Findings",
            self._render_list_lines(report.knowledge_base_findings),
        )
        self._add_section(
            lines,
            "## Historical Findings",
            self._render_list_lines(report.historical_findings),
        )
        self._add_section(
            lines,
            "## Hypotheses Considered",
            self._render_list_lines(report.hypotheses_considered),
        )
        self._add_section(lines, "## Final Root Cause", [report.root_cause])
        self._add_section(
            lines,
            "## Technical Explanation",
            [report.technical_explanation],
        )
        self._add_section(
            lines,
            "## Evidence",
            self._render_list_lines(
                [self._display_evidence_id(evidence_id) for evidence_id in report.evidence_ids]
            ),
        )
        self._add_section(
            lines,
            "## Confidence",
            [
                f"Score: {report.confidence_score}",
                "",
                f"Reason: {report.confidence_reason}",
            ],
        )
        self._add_section(
            lines,
            "## Recommended Fix",
            [report.immediate_fix or "Not specified"],
        )
        self._add_section(
            lines,
            "## Preventive Actions",
            [report.long_term_prevention or "Not specified"],
        )
        self._add_section(
            lines,
            "## Tests to Add",
            self._render_list_lines(report.tests_to_add),
        )
        self._add_section(
            lines,
            "## Open Questions",
            self._render_list_lines(report.open_questions),
        )
        self._add_section(
            lines,
            "## Low Confidence Warning",
            [report.low_confidence_warning or "None"],
        )
        self._add_section(
            lines,
            "## Generation Details",
            self._render_generation_details_lines(
                metadata=report.metadata,
                writer_key="rca_writer",
            ),
        )
        self._add_section(
            lines,
            "## Metadata",
            self._render_metadata_lines(report.metadata),
        )

        return "\n".join(lines) + "\n"

    def _build_patch_markdown(self, patch_suggestion: PatchSuggestion) -> str:
        lines: list[str] = [f"# Patch Suggestion for {patch_suggestion.incident_id}"]
        self._add_section(lines, "## Summary", [patch_suggestion.summary])
        self._add_section(
            lines,
            "## Affected Files",
            self._render_list_lines(patch_suggestion.affected_files),
        )
        self._add_section(
            lines,
            "## Behavior Changes",
            self._render_list_lines(patch_suggestion.behavior_changes),
        )
        self._add_section(
            lines,
            "## Tests to Add",
            self._render_list_lines(patch_suggestion.tests_to_add),
        )
        self._add_section(
            lines,
            "## Validation Commands",
            self._render_list_lines(patch_suggestion.validation_commands),
        )
        self._add_section(
            lines,
            "## Risk Notes",
            self._render_list_lines(patch_suggestion.risk_notes),
        )
        self._add_section(
            lines,
            "## Open Questions",
            self._render_list_lines(patch_suggestion.open_questions),
        )
        self._add_section(
            lines,
            "## Warnings",
            self._render_list_lines(patch_suggestion.warnings),
        )
        self._add_section(
            lines,
            "## File Patches",
            self._render_file_patch_lines(patch_suggestion.file_patches),
        )
        self._add_section(
            lines,
            "## Test Patches",
            self._render_file_patch_lines(patch_suggestion.test_patches),
        )
        self._add_section(
            lines,
            "## Evidence",
            self._render_list_lines(
                [
                    self._display_evidence_id(evidence_id)
                    for evidence_id in patch_suggestion.evidence_ids
                ]
            ),
        )
        self._add_section(
            lines,
            "## Approval",
            [
                f"Human approval required: {patch_suggestion.human_approval_required}",
                f"Analyze only: {str(patch_suggestion.analyze_only).lower()}",
                (
                    "Target repository modified: "
                    f"{str(patch_suggestion.target_repo_modified).lower()}"
                ),
            ],
        )
        self._add_section(
            lines,
            "## Metadata",
            [
                f"- suggestion_id: {patch_suggestion.suggestion_id}",
                f"- rca_report_id: {patch_suggestion.rca_report_id}",
                (
                    "- solution_recommendation_id: "
                    f"{patch_suggestion.solution_recommendation_id}"
                ),
                f"- confidence_score: {patch_suggestion.confidence_score}",
                *self._render_metadata_lines(patch_suggestion.metadata),
            ],
        )

        return "\n".join(lines) + "\n"

    def _build_solution_markdown(self, solution: SolutionRecommendation) -> str:
        lines: list[str] = [f"# Solution Recommendation for {solution.incident_id}"]
        self._add_section(lines, "## Summary", [solution.summary])
        self._add_section(
            lines,
            "## Immediate Steps",
            self._render_list_lines(solution.immediate_steps),
        )
        self._add_section(
            lines,
            "## Long-Term Steps",
            self._render_list_lines(solution.long_term_steps),
        )
        self._add_section(
            lines,
            "## Tests to Add",
            self._render_list_lines(solution.tests_to_add),
        )
        self._add_section(
            lines,
            "## Monitoring Improvements",
            self._render_list_lines(solution.monitoring_improvements),
        )
        self._add_section(
            lines,
            "## Risk Notes",
            self._render_list_lines(solution.risk_notes),
        )
        self._add_section(
            lines,
            "## Evidence",
            self._render_list_lines(
                [self._display_evidence_id(evidence_id) for evidence_id in solution.evidence_ids]
            ),
        )
        self._add_section(
            lines,
            "## Generation Details",
            self._render_generation_details_lines(
                metadata=solution.metadata,
                writer_key="solution_writer",
            ),
        )
        self._add_section(
            lines,
            "## Metadata",
            [
                f"- recommendation_id: {solution.recommendation_id}",
                f"- rca_report_id: {solution.rca_report_id}",
                f"- confidence_score: {solution.confidence_score}",
                *self._render_metadata_lines(solution.metadata),
            ],
        )

        return "\n".join(lines) + "\n"

    def _render_list(self, values: list[str]) -> str:
        return "\n".join(self._render_list_lines(values))

    def _render_list_lines(self, values: list[str]) -> list[str]:
        if not values:
            return ["- None"]

        lines: list[str] = []
        for value in values:
            lines.extend(self._render_list_item_lines(value))
        return lines

    def _render_list_item_lines(self, value: str) -> list[str]:
        if "\n" not in value:
            return [f"- {value}"]

        first_line, *remaining_lines = value.splitlines()
        return [
            f"- {first_line}",
            "",
            "```text",
            *remaining_lines,
            "```",
        ]

    def _render_file_patch_lines(self, file_patches: list[FilePatch]) -> list[str]:
        if not file_patches:
            return ["- None"]

        lines: list[str] = []
        for file_patch in file_patches:
            lines.append(f"- {file_patch.file_path} ({file_patch.patch_type})")
            lines.append(f"  - reason: {file_patch.reason}")
            lines.append(f"  - confidence_score: {file_patch.confidence_score}")
            if file_patch.evidence_ids:
                lines.append(f"  - evidence_ids: {', '.join(file_patch.evidence_ids)}")
            if file_patch.unified_diff:
                lines.append("")
                lines.append("```diff")
                lines.extend(file_patch.unified_diff.splitlines())
                lines.append("```")
        return lines

    def _render_metadata(self, metadata: dict[str, str]) -> str:
        return "\n".join(self._render_metadata_lines(metadata))

    def _render_metadata_lines(self, metadata: dict[str, str]) -> list[str]:
        if not metadata:
            return ["- None"]

        return [f"- {key}: {value}" for key, value in metadata.items()]

    def _render_generation_details_lines(
        self,
        *,
        metadata: dict[str, str],
        writer_key: str,
    ) -> list[str]:
        lines = [
            f"- writer: {metadata.get(writer_key, 'unknown')}",
            f"- llm_output_validated: {metadata.get('llm_output_validated', 'unknown')}",
            f"- fallback_used: {metadata.get('fallback_used', 'unknown')}",
        ]
        fallback_reason = metadata.get("fallback_reason")
        if fallback_reason:
            lines.append(f"- fallback_reason: {fallback_reason}")
        return lines

    def _add_section(
        self,
        lines: list[str],
        heading: str,
        body_lines: list[str],
    ) -> None:
        if lines:
            lines.append("")

        lines.append(heading)
        lines.append("")
        lines.extend(body_lines)

    def _display_evidence_id(self, evidence_id: str) -> str:
        value = evidence_id.removeprefix("evidence-").replace("\\", "/")
        repo_marker = "conversational_rag/"
        if repo_marker in value.lower():
            marker_index = value.lower().index(repo_marker)
            value = value[marker_index + len(repo_marker) :]

        for marker in ("src/", "tests/", "eval/", "docs/", "sample_data/"):
            if value.startswith(marker):
                break

            marker_index = value.find(f"/{marker}")
            if marker_index >= 0:
                value = value[marker_index + 1 :]
                break

        return value if evidence_id.startswith("evidence-") else evidence_id
