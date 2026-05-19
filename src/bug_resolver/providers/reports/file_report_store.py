import json
from pathlib import Path

from bug_resolver.providers.reports.base import ReportStore
from bug_resolver.schemas.rca import RCAReport
from bug_resolver.schemas.solution import SolutionRecommendation


class FileReportStore(ReportStore):
    def __init__(self, reports_dir: str | Path) -> None:
        self.reports_dir = Path(reports_dir)

    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
    ) -> list[Path]:
        report_dir = self.reports_dir / "incidents" / report.incident_id
        report_dir.mkdir(parents=True, exist_ok=True)

        json_path = report_dir / "rca.json"
        markdown_path = report_dir / "rca.md"

        self._save_json(report=report, json_path=json_path)
        self._save_markdown(report=report, markdown_path=markdown_path)

        if solution is not None:
            solution_path = report_dir / "solution.json"
            self._save_solution_json(solution=solution, json_path=solution_path)
            return [markdown_path, json_path, solution_path]

        return [markdown_path, json_path]

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

    def _save_markdown(self, report: RCAReport, markdown_path: Path) -> None:
        markdown_path.write_text(
            self._build_markdown(report),
            encoding="utf-8",
        )

    def _build_markdown(self, report: RCAReport) -> str:
        return f"""# {report.title}

## Incident Summary

{report.incident_summary}

## Impact

{report.impact or "Not specified"}

## Symptoms

{self._render_list(report.symptoms)}

## Log Findings

{self._render_list(report.log_findings)}

## Code Findings

{self._render_list(report.code_findings)}

## Knowledge Base Findings

{self._render_list(report.knowledge_base_findings)}

## Hypotheses Considered

{self._render_list(report.hypotheses_considered)}

## Final Root Cause

{report.root_cause}

## Technical Explanation

{report.technical_explanation}

## Evidence

{self._render_list(report.evidence_ids)}

## Confidence

Score: {report.confidence_score}

Reason: {report.confidence_reason}

## Recommended Fix

{report.immediate_fix or "Not specified"}

## Preventive Actions

{report.long_term_prevention or "Not specified"}

## Tests to Add

{self._render_list(report.tests_to_add)}

## Open Questions

{self._render_list(report.open_questions)}

## Low Confidence Warning

{report.low_confidence_warning or "None"}

## Metadata

{self._render_metadata(report.metadata)}
"""

    def _render_list(self, values: list[str]) -> str:
        if not values:
            return "- None"

        return "\n".join(f"- {value}" for value in values)

    def _render_metadata(self, metadata: dict[str, str]) -> str:
        if not metadata:
            return "- None"

        return "\n".join(f"- {key}: {value}" for key, value in metadata.items())
