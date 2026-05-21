"""Schemas for retrieved code context and code evidence conversion."""

from __future__ import annotations

from pydantic import Field, model_validator

from bug_resolver.schemas.common import (
    ConfidenceScore,
    EvidenceSourceType,
    StrictBaseModel,
)
from bug_resolver.schemas.evidence import EvidenceItem


class CodeContext(StrictBaseModel):
    """Retrieved source context that can be promoted to evidence."""

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
        normalized_context_id = self._normalize_context_id(self.context_id)
        metadata = self._evidence_metadata()
        return EvidenceItem(
            evidence_id=f"evidence-{normalized_context_id}",
            source_type=EvidenceSourceType.CODE,
            source_name=self.file_path,
            file_path=self.file_path,
            line_start=self.line_start,
            line_end=self.line_end,
            content=self.snippet,
            relevance_score=self.relevance_score,
            metadata=metadata,
        )

    def _evidence_metadata(self) -> dict[str, str]:
        metadata = {
            **self.metadata,
            "context_id": self.context_id,
        }

        if self.class_name:
            metadata.setdefault("class_name", self.class_name)

        if self.function_name:
            metadata.setdefault("function_name", self.function_name)

        qualified_symbol = metadata.get("qualified_symbol") or self._qualified_symbol()
        if qualified_symbol:
            metadata.setdefault("qualified_symbol", qualified_symbol)

        return metadata

    def _qualified_symbol(self) -> str | None:
        if self.class_name and self.function_name:
            return f"{self.class_name}.{self.function_name}"

        return self.function_name or self.class_name

    def _normalize_context_id(self, context_id: str) -> str:
        value = context_id.replace("\\", "/")
        repo_marker = "conversational_rag/"
        if repo_marker in value.lower():
            marker_index = value.lower().index(repo_marker)
            value = value[marker_index + len(repo_marker) :]

        for marker in ("src/", "tests/", "eval/", "docs/", "sample_data/"):
            if value.startswith(marker):
                return value

            marker_index = value.find(f"/{marker}")
            if marker_index >= 0:
                return value[marker_index + 1 :]

        return value
