"""Schema for analyze-only patch suggestions."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import ConfidenceScore, StrictBaseModel


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

    confidence_score: ConfidenceScore
    evidence_ids: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)
