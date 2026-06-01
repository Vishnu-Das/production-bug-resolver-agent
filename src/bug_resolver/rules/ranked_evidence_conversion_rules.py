"""Convert selected retrieval evidence into the workflow evidence contract."""

from __future__ import annotations

import json
from typing import Any

from bug_resolver.schemas import (
    EvidenceItem,
    EvidenceSourceType,
    IncidentDrivenContextResult,
    RankedEvidence,
    RetrievalEvidenceSourceType,
)


class RankedEvidenceConversionRules:
    """Map selected ranked evidence into legacy workflow evidence items."""

    _SOURCE_TYPE_MAP = {
        RetrievalEvidenceSourceType.LOG: EvidenceSourceType.LOG,
        RetrievalEvidenceSourceType.CODE_EXACT: EvidenceSourceType.CODE,
        RetrievalEvidenceSourceType.CODE_STRUCTURAL: EvidenceSourceType.CODE,
        RetrievalEvidenceSourceType.CODE_SEMANTIC: EvidenceSourceType.CODE,
        RetrievalEvidenceSourceType.CODE_GRAPH: EvidenceSourceType.GRAPH,
        RetrievalEvidenceSourceType.FILE_CONTEXT: EvidenceSourceType.CODE,
        RetrievalEvidenceSourceType.KNOWLEDGE_BASE: EvidenceSourceType.KNOWLEDGE_BASE,
    }

    def convert_selected(
        self,
        result: IncidentDrivenContextResult,
        *,
        agent_name: str,
        decision_id: str,
    ) -> list[EvidenceItem]:
        """Convert only selected evidence and retain compact retrieval diagnostics."""
        context_metadata = self._context_metadata(result)
        return [
            self.to_evidence_item(
                ranked_evidence,
                agent_name=agent_name,
                decision_id=decision_id,
                context_metadata=context_metadata,
            )
            for ranked_evidence in result.evaluation.selected_evidence
        ]

    def to_evidence_item(
        self,
        ranked_evidence: RankedEvidence,
        *,
        agent_name: str,
        decision_id: str,
        context_metadata: dict[str, str] | None = None,
    ) -> EvidenceItem:
        """Convert one ranked candidate into the existing evidence item schema."""
        candidate = ranked_evidence.candidate
        metadata = {
            **self._stringify_metadata(candidate.metadata),
            **(context_metadata or {}),
            "agent_name": agent_name,
            "decision_id": decision_id,
            "retriever_name": candidate.retriever_name,
            "retrieval_source_type": candidate.source_type.value,
            "rank": str(ranked_evidence.rank),
            "score": str(ranked_evidence.score.final_score),
            "score_reasons": self._json(ranked_evidence.score.reasons),
            "supporting_candidate_ids": self._json(
                ranked_evidence.supporting_candidate_ids
            ),
        }
        if candidate.retrieval_query is not None:
            metadata["retrieval_query"] = candidate.retrieval_query
        if candidate.symbol_name is not None:
            metadata["symbol_name"] = candidate.symbol_name
        if candidate.symbol_type is not None:
            metadata["symbol_type"] = candidate.symbol_type

        return EvidenceItem(
            evidence_id=candidate.candidate_id,
            source_type=self._SOURCE_TYPE_MAP[candidate.source_type],
            source_name=(
                candidate.file_path
                or candidate.symbol_name
                or candidate.retriever_name
            ),
            content=candidate.content,
            file_path=candidate.file_path,
            line_start=candidate.start_line,
            line_end=candidate.end_line,
            relevance_score=ranked_evidence.score.final_score,
            confidence=ranked_evidence.score.final_score,
            metadata=metadata,
        )

    def _context_metadata(
        self,
        result: IncidentDrivenContextResult,
    ) -> dict[str, str]:
        plan = result.retrieval_plan
        metadata = {
            "incident_facts_summary": result.facts.summary,
            "retrieval_plan_summary": self._json(
                {
                    "anchors": len(plan.anchors),
                    "exact_queries": len(plan.exact_queries),
                    "structural_queries": len(plan.structural_queries),
                    "semantic_queries": len(plan.semantic_queries),
                    "file_context_requests": len(plan.file_context_requests),
                    "graph_expansion_requests": len(plan.graph_expansion_requests),
                    "kb_queries": len(plan.kb_queries),
                }
            ),
            "selected_scores": self._json(
                [
                    ranked_evidence.score.final_score
                    for ranked_evidence in result.evaluation.selected_evidence
                ]
            ),
            "retrieval_sufficient_for_rca": str(
                result.evaluation.sufficient_for_rca
            ).lower(),
            "retrieval_confidence": str(result.evaluation.confidence),
        }
        if result.evaluation.missing_evidence:
            metadata["retrieval_missing_evidence"] = self._json(
                result.evaluation.missing_evidence
            )
        if result.evaluation.warnings:
            metadata["retrieval_evaluation_warnings"] = self._json(
                result.evaluation.warnings
            )
        if result.failed_retrievers:
            metadata["failed_retrievers"] = self._json(result.failed_retrievers)
        if result.retrieval_warnings:
            metadata["retrieval_warnings"] = self._json(result.retrieval_warnings)
        return metadata

    def _stringify_metadata(self, metadata: dict[str, Any]) -> dict[str, str]:
        return {
            str(key): self._stringify(value)
            for key, value in metadata.items()
            if value is not None
        }

    def _stringify(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list, tuple, set)):
            return self._json(value)
        return str(value)

    def _json(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, default=str)
