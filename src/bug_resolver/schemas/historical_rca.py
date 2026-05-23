"""Schema for historical RCA context used as incident memory."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import EvidenceSourceType, StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem


class HistoricalRCAContext(StrictBaseModel):
    """Relevant prior RCA report returned by historical RCA providers."""

    context_id: str = Field(..., min_length=1)
    incident_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    root_cause: str = Field(..., min_length=1)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    report_path: str | None = None
    matched_signals: list[str] = Field(default_factory=list)
    content: str = Field(..., min_length=1)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_evidence_item(self) -> EvidenceItem:
        """Convert historical context into normalized supporting evidence."""
        return EvidenceItem(
            evidence_id=f"historical-{self.incident_id}",
            source_type=EvidenceSourceType.HISTORICAL_RCA,
            source_name=self.title,
            content=self.content,
            file_path=self.report_path,
            relevance_score=self.relevance_score,
            confidence=self.confidence_score,
            metadata={
                "historical_incident_id": self.incident_id,
                "matched_signals": ", ".join(self.matched_signals),
                "historical_context_only": "true",
            },
        )
