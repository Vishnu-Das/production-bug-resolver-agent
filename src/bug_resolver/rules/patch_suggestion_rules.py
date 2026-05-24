"""Deterministic rules for analyze-only patch suggestions."""

from __future__ import annotations

import re

from bug_resolver.schemas import PatchSuggestion, RCAReport, SolutionRecommendation
from bug_resolver.signals.patch_suggestion_signals import (
    DIRECT_CHANGE_TERMS,
    DIRECT_OWNER_FIELDS,
    PATCH_OWNER_OVERRIDE_TERMS,
    PATCH_OWNER_TERMS,
    SUPPORT_CONTEXT_TERMS,
    VALIDATION_STEP_PREFIXES,
    VALIDATION_STEP_TERMS,
)
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
            affected_files=self.affected_files_for_reports(
                rca_report=rca_report,
                solution=solution,
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
                    self.supporting_context_files_for_reports(
                        rca_report=rca_report,
                        solution=solution,
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

    def affected_files_for_reports(
        self,
        *,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> list[str]:
        evidence_ids = self.unique([*rca_report.evidence_ids, *solution.evidence_ids])
        all_paths = self.affected_files(evidence_ids)
        patch_owner_paths = [
            path
            for path in all_paths
            if self._is_patch_owner_path(
                path=path,
                rca_report=rca_report,
                solution=solution,
            )
        ]
        return patch_owner_paths or all_paths[:2]

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

    def supporting_context_files_for_reports(
        self,
        *,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> list[str]:
        evidence_ids = self.unique([*rca_report.evidence_ids, *solution.evidence_ids])
        affected_files = set(
            self.affected_files_for_reports(
                rca_report=rca_report,
                solution=solution,
            )
        )
        paths = self.supporting_context_files(evidence_ids)
        paths.extend(
            path
            for path in self.affected_files(evidence_ids)
            if path not in affected_files
        )
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
        return normalized.startswith(VALIDATION_STEP_PREFIXES) or any(
            term in normalized for term in VALIDATION_STEP_TERMS
        )

    def _is_patch_owner_path(
        self,
        *,
        path: str,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> bool:
        path_mentions = self._path_mentions(
            path=path,
            rca_report=rca_report,
            solution=solution,
        )
        if not path_mentions:
            return False

        if self._has_direct_change_mention(
            path=path,
            rca_report=rca_report,
            solution=solution,
        ):
            return True

        owner_mentions = [
            value
            for field_name, value in path_mentions
            if self._is_direct_owner_field(field_name)
            or not self._is_supporting_mention(value)
        ]
        if not owner_mentions:
            return False

        return any(self._has_patch_owner_signal(value) for value in owner_mentions)

    def _has_direct_change_mention(
        self,
        *,
        path: str,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> bool:
        display_path = path.lower()
        symbolless_path = path.split(":", maxsplit=1)[0].lower()
        values = [
            rca_report.immediate_fix or "",
            rca_report.long_term_prevention or "",
            solution.summary,
            *solution.immediate_steps,
        ]
        return any(
            (
                display_path in value.lower() or symbolless_path in value.lower()
            )
            and any(term in value.lower() for term in DIRECT_CHANGE_TERMS)
            for value in values
        )

    def _path_mentions(
        self,
        *,
        path: str,
        rca_report: RCAReport,
        solution: SolutionRecommendation,
    ) -> list[tuple[str, str]]:
        display_path = path.lower()
        symbolless_path = path.split(":", maxsplit=1)[0].lower()
        values: list[tuple[str, str]] = [
            *[("code_findings", value) for value in rca_report.code_findings],
            *[("graph_findings", value) for value in rca_report.graph_findings],
            ("root_cause", rca_report.root_cause),
            ("technical_explanation", rca_report.technical_explanation),
            ("immediate_fix", rca_report.immediate_fix or ""),
            ("long_term_prevention", rca_report.long_term_prevention or ""),
            ("solution_summary", solution.summary),
            *[("solution_step", value) for value in solution.immediate_steps],
        ]
        return [
            (field_name, excerpt)
            for field_name, value in values
            for excerpt in self._matching_path_excerpts(
                value=value,
                display_path=display_path,
                symbolless_path=symbolless_path,
            )
        ]

    def _matching_path_excerpts(
        self,
        *,
        value: str,
        display_path: str,
        symbolless_path: str,
    ) -> list[str]:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", value)
            if sentence.strip()
        ] or [value]
        return [
            sentence
            for sentence in sentences
            if display_path in sentence.lower() or symbolless_path in sentence.lower()
        ]

    def _is_direct_owner_field(self, field_name: str) -> bool:
        return field_name in DIRECT_OWNER_FIELDS

    def _is_supporting_mention(self, value: str) -> bool:
        normalized = value.lower()
        has_support_signal = any(term in normalized for term in SUPPORT_CONTEXT_TERMS)
        return has_support_signal and not self._has_patch_owner_override(normalized)

    def _has_patch_owner_signal(self, value: str) -> bool:
        normalized = value.lower()
        return any(term in normalized for term in PATCH_OWNER_TERMS)

    def _has_patch_owner_override(self, value: str) -> bool:
        normalized = value.lower()
        return any(term in normalized for term in PATCH_OWNER_OVERRIDE_TERMS)

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
