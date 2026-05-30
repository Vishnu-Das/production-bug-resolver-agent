"""Schemas for incident-driven retrieval planning."""

from __future__ import annotations

from pydantic import Field, model_validator

from bug_resolver.schemas.common import ConfidenceScore, StrictBaseModel
from bug_resolver.schemas.evidence_scoring import EvidenceCandidate


class StackFrame(StrictBaseModel):
    """A stack-frame location parsed from incident or runtime text."""

    file_path: str = Field(..., min_length=1)
    line_number: int | None = Field(default=None, ge=1)
    function_name: str | None = None
    class_name: str | None = None


class IncidentFacts(StrictBaseModel):
    """Structured facts extracted from the incident and runtime evidence."""

    incident_id: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    description: str | None = None
    error_terms: list[str] = Field(default_factory=list)
    exception_types: list[str] = Field(default_factory=list)
    stack_frames: list[StackFrame] = Field(default_factory=list)
    status_codes: list[int] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    request_ids: list[str] = Field(default_factory=list)
    candidate_symbols: list[str] = Field(default_factory=list)
    quoted_terms: list[str] = Field(default_factory=list)
    config_like_terms: list[str] = Field(default_factory=list)


class RetrievalAnchor(StrictBaseModel):
    """A grounded fact used to plan retrieval."""

    value: str = Field(..., min_length=1)
    anchor_type: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    file_path: str | None = None
    line_number: int | None = Field(default=None, ge=1)
    confidence: ConfidenceScore = 1.0


class RetrievalQuery(StrictBaseModel):
    """A query sent to a specific retrieval route."""

    query: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    priority: int = 0
    source_hint: str | None = None


class FileContextRequest(StrictBaseModel):
    """Request for surrounding source lines around a grounded file location."""

    file_path: str = Field(..., min_length=1)
    line_number: int | None = Field(default=None, ge=1)
    before_lines: int = Field(default=40, ge=0)
    after_lines: int = Field(default=40, ge=0)
    reason: str = Field(..., min_length=1)


class GraphExpansionRequest(StrictBaseModel):
    """Request to expand structural code context from a file, symbol, or line."""

    file_path: str | None = None
    symbol_name: str | None = None
    line_number: int | None = Field(default=None, ge=1)
    max_depth: int = Field(default=1, ge=1)
    reason: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_expansion_anchor(self) -> GraphExpansionRequest:
        if self.file_path is None and self.symbol_name is None and self.line_number is None:
            raise ValueError(
                "at least one of file_path, symbol_name, or line_number must be present"
            )
        return self


class RetrievalPlan(StrictBaseModel):
    """Planned retrieval work derived from incident facts and anchors."""

    anchors: list[RetrievalAnchor] = Field(default_factory=list)
    exact_queries: list[RetrievalQuery] = Field(default_factory=list)
    structural_queries: list[RetrievalQuery] = Field(default_factory=list)
    semantic_queries: list[RetrievalQuery] = Field(default_factory=list)
    file_context_requests: list[FileContextRequest] = Field(default_factory=list)
    graph_expansion_requests: list[GraphExpansionRequest] = Field(default_factory=list)
    kb_queries: list[RetrievalQuery] = Field(default_factory=list)


class RetrievalProviderFailure(StrictBaseModel):
    """A provider route that failed while parallel context retrieval continued."""

    route: str = Field(..., min_length=1)
    provider_name: str = Field(..., min_length=1)
    error_type: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class RetrievalBatchResult(StrictBaseModel):
    """Raw evidence candidates and recoverable failures from retrieval routes."""

    candidates: list[EvidenceCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failed_retrievers: list[str] = Field(default_factory=list)
    failures: list[RetrievalProviderFailure] = Field(default_factory=list)
