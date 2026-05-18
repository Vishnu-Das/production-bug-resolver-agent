from __future__ import annotations

from pydantic import Field, model_validator

from bug_resolver.schemas.common import (
    ConfidenceScore,
    EvidenceSourceType,
    StrictBaseModel,
)


class EvidenceItem(StrictBaseModel):
    evidence_id: str = Field(..., min_length=1)

    source_type: EvidenceSourceType
    source_name: str = Field(..., min_length=1)

    content: str = Field(..., min_length=1)

    file_path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    relevance_score: ConfidenceScore | None = None
    confidence: ConfidenceScore | None = None

    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_line_range(self) -> EvidenceItem:
        if self.line_start is not None and self.line_end is not None:
            if self.line_end < self.line_start:
                raise ValueError("line_end must be greater than or equal to line_start")
        return self