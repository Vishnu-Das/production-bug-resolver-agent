"""Schema for candidate RCA hypotheses."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import (
    ConfidenceScore,
    HypothesisStatus,
    StrictBaseModel,
)


class Hypothesis(StrictBaseModel):
    """Candidate root-cause hypothesis with confidence and supporting evidence."""

    hypothesis_id: str = Field(..., min_length=1)

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)

    suspected_root_cause: str = Field(..., min_length=1)

    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)

    confidence_score: ConfidenceScore
    status: HypothesisStatus = HypothesisStatus.PROPOSED

    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
