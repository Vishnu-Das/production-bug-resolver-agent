"""Schema for evidence sufficiency evaluation results."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import ConfidenceScore, StrictBaseModel


class EvidenceEvaluationResult(StrictBaseModel):
    """Result of deterministic evidence sufficiency evaluation."""

    evaluation_id: str = Field(..., min_length=1)
    incident_id: str = Field(..., min_length=1)

    confidence_score: ConfidenceScore
    retry_required: bool = False
    can_write_rca: bool = False

    missing_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    improved_code_queries: list[str] = Field(default_factory=list)
    improved_knowledge_queries: list[str] = Field(default_factory=list)

    reason: str = Field(..., min_length=1)
