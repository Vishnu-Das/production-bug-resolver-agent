"""Schema for analyze-only patch suggestions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from bug_resolver.schemas.common import ConfidenceScore, StrictBaseModel


class FilePatch(StrictBaseModel):
    """Future-ready file patch container for human-reviewed diffs."""

    file_path: str = Field(..., min_length=1)
    patch_type: Literal["modify", "create", "delete"]
    unified_diff: str = ""
    reason: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence_score: ConfidenceScore


class PatchSuggestion(StrictBaseModel):
    """Human-reviewable patch plan derived from RCA and solution evidence."""

    suggestion_id: str = Field(..., min_length=1)
    incident_id: str = Field(..., min_length=1)
    rca_report_id: str = Field(..., min_length=1)
    solution_recommendation_id: str = Field(..., min_length=1)

    summary: str = Field(..., min_length=1)
    affected_files: list[str] = Field(default_factory=list)
    behavior_changes: list[str] = Field(default_factory=list)
    tests_to_add: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    file_patches: list[FilePatch] = Field(default_factory=list)
    test_patches: list[FilePatch] = Field(default_factory=list)

    confidence_score: ConfidenceScore
    evidence_ids: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    analyze_only: bool = True
    target_repo_modified: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)
