"""Adapter from existing knowledge-base search to retrieval evidence candidates."""

from __future__ import annotations

import hashlib
from typing import Any

from bug_resolver.providers.knowledge import KnowledgeBaseProvider
from bug_resolver.providers.retrieval.base import KnowledgeSearchProvider
from bug_resolver.schemas import (
    EvidenceCandidate,
    KnowledgeContext,
    RetrievalEvidenceSourceType,
    RetrievalQuery,
)
from bug_resolver.utils.observability import get_logger, traceable

logger = get_logger(__name__)


class KnowledgeSearchAdapter(KnowledgeSearchProvider):
    """Expose the existing knowledge-base provider through the retrieval pipeline."""

    def __init__(
        self,
        knowledge_base_provider: KnowledgeBaseProvider,
        *,
        retriever_name: str = "knowledge_search",
        max_results_per_query: int = 5,
    ) -> None:
        if max_results_per_query < 1:
            raise ValueError("max_results_per_query must be greater than zero")

        self._knowledge_base_provider = knowledge_base_provider
        self._retriever_name = retriever_name
        self._max_results_per_query = max_results_per_query

    @traceable(name="knowledge_search.search_knowledge", run_type="retriever")
    async def search_knowledge(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        """Convert knowledge contexts into raw candidates without reranking them."""
        candidates: list[EvidenceCandidate] = []
        seen_candidate_ids: set[str] = set()

        for query in queries:
            query_text = query.query.strip()
            if not query_text:
                continue

            try:
                contexts = await self._knowledge_base_provider.search_knowledge(
                    [query_text],
                    limit=self._max_results_per_query,
                )
            except Exception as error:
                logger.warning(
                    "knowledge search failed query=%s error=%s",
                    query_text,
                    error,
                )
                continue

            for context in contexts:
                candidate = self._to_candidate(context, query)
                if candidate is None or candidate.candidate_id in seen_candidate_ids:
                    continue

                seen_candidate_ids.add(candidate.candidate_id)
                candidates.append(candidate)

        return candidates

    def _to_candidate(
        self,
        context: KnowledgeContext,
        query: RetrievalQuery,
    ) -> EvidenceCandidate | None:
        content = context.content.strip()
        if not content:
            return None

        metadata: dict[str, Any] = {
            **context.metadata,
            "purpose": query.purpose,
            "priority": query.priority,
            "document_title": context.document_name,
            "original_context_id": context.context_id,
        }
        if query.source_hint is not None:
            metadata["source_hint"] = query.source_hint
        if context.section_title is not None:
            metadata["section"] = context.section_title
        if context.relevance_score is not None:
            metadata["score"] = context.relevance_score
        metadata.setdefault("provider", type(self._knowledge_base_provider).__name__)

        return EvidenceCandidate(
            candidate_id=self._candidate_id(context, query.query),
            source_type=RetrievalEvidenceSourceType.KNOWLEDGE_BASE,
            retriever_name=self._retriever_name,
            content=content,
            file_path=context.file_path,
            start_line=self._metadata_int(context.metadata, "start_line", "line_start"),
            end_line=self._metadata_int(context.metadata, "end_line", "line_end"),
            retrieval_query=query.query,
            metadata=metadata,
        )

    def _metadata_int(
        self,
        metadata: dict[str, str],
        *keys: str,
    ) -> int | None:
        for key in keys:
            value = metadata.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except ValueError:
                logger.warning(
                    "knowledge search ignored invalid line metadata key=%s value=%s",
                    key,
                    value,
                )
        return None

    def _candidate_id(self, context: KnowledgeContext, query: str) -> str:
        identity = f"knowledge_base:{context.context_id}:{context.file_path}:{query}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
        return f"EVID-KB-{digest}"
