"""Schemas for evidence candidates, scoring, and ranked selection."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from bug_resolver.schemas.common import ConfidenceScore, StrictBaseModel


class EvidenceSourceType(StrEnum):
    """Retriever-level evidence source categories for ranked evidence."""

    LOG = "log"
    CODE_EXACT = "code_exact"
    CODE_STRUCTURAL = "code_structural"
    CODE_SEMANTIC = "code_semantic"
    CODE_GRAPH = "code_graph"
    FILE_CONTEXT = "file_context"
    KNOWLEDGE_BASE = "knowledge_base"


class EvidenceCandidate(StrictBaseModel):
    """Normalized evidence candidate before deterministic ranking."""

    candidate_id: str = Field(..., min_length=1)
    source_type: EvidenceSourceType
    retriever_name: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    file_path: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    symbol_name: str | None = None
    symbol_type: str | None = None
    matched_terms: list[str] = Field(default_factory=list)
    retrieval_query: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_line_range(self) -> EvidenceCandidate:
        if self.start_line is not None and self.end_line is not None:
            if self.end_line < self.start_line:
                raise ValueError("end_line must be greater than or equal to start_line")
        return self


class EvidenceScoreBreakdown(StrictBaseModel):
    """Repo-agnostic scoring dimensions for ranked evidence."""

    source_strength: float = 0.0
    directness: float = 0.0
    incident_term_overlap: float = 0.0
    exact_error_match: float = 0.0
    file_path_match: float = 0.0
    symbol_match: float = 0.0
    stack_trace_proximity: float = 0.0
    line_proximity: float = 0.0
    graph_distance_score: float = 0.0
    multi_source_agreement: float = 0.0
    recency_relevance: float = 0.0
    semantic_only_penalty: float = 0.0
    noise_penalty: float = 0.0
    final_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class RankedEvidence(StrictBaseModel):
    """A scored evidence candidate with its final rank."""

    candidate: EvidenceCandidate
    score: EvidenceScoreBreakdown
    rank: int = Field(..., ge=1)
    supporting_candidate_ids: list[str] = Field(default_factory=list)


class EvidenceEvaluationResult(StrictBaseModel):
    """Result of candidate ranking and evidence selection."""

    ranked_evidence: list[RankedEvidence] = Field(default_factory=list)
    selected_evidence: list[RankedEvidence] = Field(default_factory=list)
    has_runtime_evidence: bool = False
    has_direct_code_evidence: bool = False
    has_supporting_kb_evidence: bool = False
    has_graph_support: bool = False
    sufficient_for_rca: bool = False
    confidence: ConfidenceScore = 0.0
    missing_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
