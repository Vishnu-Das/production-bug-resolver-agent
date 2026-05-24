"""Deterministic rules for analyze-only patch suggestions."""

from __future__ import annotations

from bug_resolver.schemas import PatchSuggestion, RCAReport, SolutionRecommendation
from bug_resolver.utils.ids import new_patch_suggestion_id


class PatchSuggestionRules:
    """Build a human-reviewable patch plan without modifying target repositories."""

    def build_patch_suggestion(
        self,
        *,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> PatchSuggestion:
        """Create a deterministic patch suggestion from RCA and solution outputs."""
        return PatchSuggestion(
            suggestion_id=new_patch_suggestion_id(),
            incident_id=rca_report.incident_id,
            rca_report_id=rca_report.report_id,
            solution_recommendation_id=solution.recommendation_id,
            summary=self.build_summary(rca_report),
            affected_files=self.affected_files(
                [*rca_report.evidence_ids, *solution.evidence_ids]
            ),
            behavior_changes=self.behavior_changes(rca_report, solution),
            tests_to_add=self.tests_to_add(rca_report, solution),
            validation_commands=self.validation_commands(),
            risk_notes=self.risk_notes(rca_report, solution),
            open_questions=self.open_questions(rca_report),
            file_patches=[],
            test_patches=[],
            confidence_score=min(rca_report.confidence_score, solution.confidence_score),
            evidence_ids=self.unique([*rca_report.evidence_ids, *solution.evidence_ids]),
            human_approval_required=True,
            analyze_only=True,
            target_repo_modified=False,
            metadata={
                "patch_suggestion_writer": "deterministic",
                "analyze_only": "true",
                "target_repo_modified": "false",
                "supporting_context_files": ", ".join(
                    self.supporting_context_files(
                        [*rca_report.evidence_ids, *solution.evidence_ids]
                    )
                ),
            },
        )

    def build_summary(self, rca_report: RCAReport) -> str:
        return (
            "Analyze-only patch plan for "
            f"{rca_report.incident_id}: {rca_report.root_cause}"
        )

    def affected_files(self, evidence_ids: list[str]) -> list[str]:
        paths: list[str] = []
        for evidence_id in evidence_ids:
            path = self._path_from_evidence_id(
                evidence_id,
                allow_graph=False,
            )
            if path is not None:
                paths.append(path)
        return self.unique(paths)

    def supporting_context_files(self, evidence_ids: list[str]) -> list[str]:
        paths: list[str] = []
        for evidence_id in evidence_ids:
            path = self._path_from_evidence_id(
                evidence_id,
                allow_graph=True,
            )
            if path is None or path in self.affected_files(evidence_ids):
                continue
            paths.append(path)
        return self.unique(paths)

    def behavior_changes(
        self,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> list[str]:
        changes: list[str] = []
        if rca_report.immediate_fix:
            changes.append(rca_report.immediate_fix)
        changes.extend(
            step for step in solution.immediate_steps if not self._is_validation_step(step)
        )
        return self.unique(changes)

    def tests_to_add(
        self,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> list[str]:
        return self.unique([*rca_report.tests_to_add, *solution.tests_to_add])

    def validation_commands(self) -> list[str]:
        return [
            "Run the target repository's focused unit tests for the affected files.",
            "Run the target repository's relevant integration or regression tests.",
            "Run the production-bug-resolver-agent investigation again for this incident.",
        ]

    def risk_notes(
        self,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> list[str]:
        risks = [
            "Human approval is required before applying this patch plan.",
            "This plan does not modify code, create commits, or open pull requests.",
        ]
        risks.extend(solution.risk_notes)
        return self.unique(risks)

    def open_questions(self, rca_report: RCAReport) -> list[str]:
        return self.unique(rca_report.open_questions)

    def _path_from_evidence_id(
        self,
        evidence_id: str,
        *,
        allow_graph: bool,
    ) -> str | None:
        normalized = evidence_id.replace("\\", "/")
        if normalized.startswith("evidence-"):
            normalized = normalized.removeprefix("evidence-")
        elif allow_graph and normalized.startswith("graph-"):
            normalized = normalized.removeprefix("graph-")
        else:
            return None

        if not normalized.startswith(("src/", "app/", "services/", "lib/")):
            return None

        path = normalized.split(":", maxsplit=1)[0]
        if path.endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
            return path
        return None

    def _is_validation_step(self, value: str) -> bool:
        normalized = value.strip().lower()
        validation_prefixes = (
            "run ",
            "validate ",
            "verify ",
            "confirm ",
            "reproduce ",
            "test ",
            "monitor ",
        )
        validation_terms = (
            "test",
            "validation",
            "verify",
            "reproduce",
            "confirm",
            "monitoring",
        )
        return normalized.startswith(validation_prefixes) or any(
            term in normalized for term in validation_terms
        )

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
