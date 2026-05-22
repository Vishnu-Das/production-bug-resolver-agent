"""Schemas for AST-derived code graph context and evidence conversion."""

from __future__ import annotations

from pydantic import Field, model_validator

from bug_resolver.schemas.common import (
    ConfidenceScore,
    EvidenceSourceType,
    StrictBaseModel,
)
from bug_resolver.schemas.evidence import EvidenceItem


class CodeGraphContext(StrictBaseModel):
    """Structural code context for symbols, calls, imports, and config reads."""

    context_id: str = Field(..., min_length=1)

    file_path: str = Field(..., min_length=1)
    relative_path: str = Field(..., min_length=1)
    symbol_name: str = Field(..., min_length=1)
    symbol_type: str = Field(..., min_length=1)
    qualified_symbol: str = Field(..., min_length=1)

    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    calls: list[str] = Field(default_factory=list)
    called_by: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    config_keys: list[str] = Field(default_factory=list)
    config_readers: list[str] = Field(default_factory=list)

    content: str = Field(..., min_length=1)
    retrieval_query: str | None = None
    relevance_score: ConfidenceScore | None = None

    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_line_range(self) -> CodeGraphContext:
        if self.line_start is not None and self.line_end is not None:
            if self.line_end < self.line_start:
                raise ValueError("line_end must be greater than or equal to line_start")
        return self

    def to_evidence_item(self) -> EvidenceItem:
        """Convert graph context into structured evidence for the workflow."""
        metadata = {
            **self.metadata,
            "context_id": self.context_id,
            "relative_path": self.relative_path,
            "symbol_name": self.symbol_name,
            "symbol_type": self.symbol_type,
            "qualified_symbol": self.qualified_symbol,
        }

        if self.calls:
            metadata["calls"] = ", ".join(self.calls)
        if self.called_by:
            metadata["called_by"] = ", ".join(self.called_by)
        if self.imports:
            metadata["imports"] = ", ".join(self.imports)
        if self.imported_by:
            metadata["imported_by"] = ", ".join(self.imported_by)
        if self.config_keys:
            metadata["config_keys"] = ", ".join(self.config_keys)
        if self.config_readers:
            metadata["config_readers"] = ", ".join(self.config_readers)

        return EvidenceItem(
            evidence_id=f"graph-{self._normalize_context_id(self.context_id)}",
            source_type=EvidenceSourceType.GRAPH,
            source_name=self.file_path,
            file_path=self.file_path,
            line_start=self.line_start,
            line_end=self.line_end,
            content=self.content,
            relevance_score=self.relevance_score,
            metadata=metadata,
        )

    def _normalize_context_id(self, context_id: str) -> str:
        value = context_id.replace("\\", "/")
        for marker in ("src/", "tests/", "eval/", "docs/", "sample_data/"):
            if value.startswith(marker):
                return value

            marker_index = value.find(f"/{marker}")
            if marker_index >= 0:
                return value[marker_index + 1 :]

        return value
