from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import ConfidenceScore, StrictBaseModel


class SolutionRecommendation(StrictBaseModel):
    recommendation_id: str = Field(..., min_length=1)
    incident_id: str = Field(..., min_length=1)
    rca_report_id: str = Field(..., min_length=1)

    summary: str = Field(..., min_length=1)

    immediate_steps: list[str] = Field(default_factory=list)
    long_term_steps: list[str] = Field(default_factory=list)
    tests_to_add: list[str] = Field(default_factory=list)
    monitoring_improvements: list[str] = Field(default_factory=list)

    risk_notes: list[str] = Field(default_factory=list)
    confidence_score: ConfidenceScore

    evidence_ids: list[str] = Field(default_factory=list)