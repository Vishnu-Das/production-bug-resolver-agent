from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import (
    ConfidenceScore,
    EvidenceSourceType,
    StrictBaseModel,
)
from bug_resolver.schemas.evidence import EvidenceItem


class KnowledgeContext(StrictBaseModel):
    context_id: str = Field(..., min_length=1)

    document_name: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

    section_title: str | None = None
    file_path: str | None = None

    retrieval_query: str | None = None
    relevance_score: ConfidenceScore | None = None

    metadata: dict[str, str] = Field(default_factory=dict)

    def to_evidence_item(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"evidence-{self.context_id}",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name=self.document_name,
            file_path=self.file_path,
            content=self.content,
            relevance_score=self.relevance_score,
            metadata={
                **self.metadata,
                "context_id": self.context_id,
                "section_title": self.section_title or "",
            },
        )