from __future__ import annotations

from pydantic import Field, model_validator

from bug_resolver.schemas.common import (
    ConfidenceScore,
    EvidenceSourceType,
    StrictBaseModel,
)
from bug_resolver.schemas.evidence import EvidenceItem


class CodeContext(StrictBaseModel):
    context_id: str = Field(..., min_length=1)

    file_path: str = Field(..., min_length=1)
    snippet: str = Field(..., min_length=1)

    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    class_name: str | None = None
    function_name: str | None = None

    retrieval_query: str | None = None
    relevance_score: ConfidenceScore | None = None

    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_line_range(self) -> CodeContext:
        if self.line_start is not None and self.line_end is not None:
            if self.line_end < self.line_start:
                raise ValueError("line_end must be greater than or equal to line_start")
        return self

    def to_evidence_item(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"evidence-{self.context_id}",
            source_type=EvidenceSourceType.CODE,
            source_name=self.file_path,
            file_path=self.file_path,
            line_start=self.line_start,
            line_end=self.line_end,
            content=self.snippet,
            relevance_score=self.relevance_score,
            metadata={
                **self.metadata,
                "context_id": self.context_id,
            },
        )