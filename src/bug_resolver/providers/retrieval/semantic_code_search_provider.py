"""Adapter from existing semantic code context search to retrieval evidence candidates."""

from __future__ import annotations

import hashlib
from typing import Any

from bug_resolver.providers.code import CodeContextProvider
from bug_resolver.providers.retrieval.base import SemanticCodeSearchProvider
from bug_resolver.schemas import (
    CodeContext,
    EvidenceCandidate,
    RetrievalEvidenceSourceType,
    RetrievalQuery,
)
from bug_resolver.utils.observability import get_logger, traceable

logger = get_logger(__name__)


class SemanticCodeSearchAdapter(SemanticCodeSearchProvider):
    """Expose the existing semantic code provider through the retrieval pipeline."""

    def __init__(
        self,
        code_context_provider: CodeContextProvider,
        *,
        retriever_name: str = "semantic_code_search",
        max_results_per_query: int = 10,
    ) -> None:
        if max_results_per_query < 1:
            raise ValueError("max_results_per_query must be greater than zero")

        self._code_context_provider = code_context_provider
        self._retriever_name = retriever_name
        self._max_results_per_query = max_results_per_query

    @traceable(name="semantic_code_search.search_semantic_code", run_type="retriever")
    async def search_semantic_code(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        """Convert semantic code contexts into raw candidates without reranking them."""
        candidates: list[EvidenceCandidate] = []
        seen_candidate_ids: set[str] = set()

        for query in queries:
            query_text = query.query.strip()
            if not query_text:
                continue

            try:
                contexts = await self._code_context_provider.search_code(
                    [query_text],
                    limit=self._max_results_per_query,
                )
            except Exception as error:
                logger.warning(
                    "semantic code search failed query=%s error=%s",
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
        context: CodeContext,
        query: RetrievalQuery,
    ) -> EvidenceCandidate | None:
        content = context.snippet.strip()
        if not content:
            return None

        metadata: dict[str, Any] = {
            **context.metadata,
            "purpose": query.purpose,
            "priority": query.priority,
            "original_context_id": context.context_id,
        }
        if query.source_hint is not None:
            metadata["source_hint"] = query.source_hint
        if context.relevance_score is not None:
            metadata["semantic_score"] = context.relevance_score
        if context.class_name is not None:
            metadata.setdefault("class_name", context.class_name)
        if context.function_name is not None:
            metadata.setdefault("function_name", context.function_name)
        metadata.setdefault("provider", type(self._code_context_provider).__name__)
        symbol_name = self._symbol_name(context)
        if symbol_name is not None:
            metadata.setdefault("qualified_symbol", symbol_name)

        return EvidenceCandidate(
            candidate_id=self._candidate_id(context, query.query),
            source_type=RetrievalEvidenceSourceType.CODE_SEMANTIC,
            retriever_name=self._retriever_name,
            content=content,
            file_path=context.file_path,
            start_line=context.line_start,
            end_line=context.line_end,
            symbol_name=symbol_name,
            symbol_type=context.metadata.get("symbol_type"),
            retrieval_query=query.query,
            metadata=metadata,
        )

    def _symbol_name(self, context: CodeContext) -> str | None:
        return (
            context.metadata.get("qualified_symbol")
            or context.function_name
            or context.class_name
        )

    def _candidate_id(self, context: CodeContext, query: str) -> str:
        identity = (
            f"code_semantic:{context.context_id}:{context.file_path}:"
            f"{context.line_start}:{context.line_end}:{query}"
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
        return f"EVID-SEMANTIC-{digest}"
