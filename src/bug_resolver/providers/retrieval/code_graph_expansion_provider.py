"""Adapter from existing AST code graph search to retrieval evidence candidates."""

from __future__ import annotations

import hashlib
from typing import Any

from bug_resolver.providers.graph import CodeGraphProvider
from bug_resolver.providers.retrieval.base import CodeGraphExpansionProvider
from bug_resolver.schemas import (
    CodeGraphContext,
    EvidenceCandidate,
    GraphExpansionRequest,
    RetrievalEvidenceSourceType,
)
from bug_resolver.utils.observability import get_logger, traceable

logger = get_logger(__name__)


class CodeGraphExpansionAdapter(CodeGraphExpansionProvider):
    """Expose the existing AST code graph provider through the retrieval pipeline."""

    def __init__(
        self,
        code_graph_provider: CodeGraphProvider,
        *,
        retriever_name: str = "code_graph_expansion",
        max_results_per_request: int = 10,
    ) -> None:
        if max_results_per_request < 1:
            raise ValueError("max_results_per_request must be greater than zero")

        self._code_graph_provider = code_graph_provider
        self._retriever_name = retriever_name
        self._max_results_per_request = max_results_per_request

    @traceable(name="code_graph_expansion.expand_context", run_type="retriever")
    async def expand_context(
        self,
        requests: list[GraphExpansionRequest],
    ) -> list[EvidenceCandidate]:
        """Convert graph contexts into raw candidates without reranking them."""
        candidates: list[EvidenceCandidate] = []
        seen_candidate_ids: set[str] = set()

        for request in requests:
            query = self._query_from_request(request)
            if query is None:
                logger.info(
                    "code graph expansion skipped request without searchable file or symbol"
                )
                continue

            try:
                contexts = await self._code_graph_provider.search_graph(
                    [query],
                    limit=self._max_results_per_request,
                )
            except Exception as error:
                logger.warning(
                    "code graph expansion failed query=%s error=%s",
                    query,
                    error,
                )
                continue

            for context in contexts:
                candidate = self._to_candidate(context, request, query)
                if candidate.candidate_id in seen_candidate_ids:
                    continue

                seen_candidate_ids.add(candidate.candidate_id)
                candidates.append(candidate)

        return candidates

    def _to_candidate(
        self,
        context: CodeGraphContext,
        request: GraphExpansionRequest,
        query: str,
    ) -> EvidenceCandidate:
        graph_distance = self._graph_distance(context, request)
        relationship_types = self._relationship_types(context)
        metadata: dict[str, Any] = {
            **context.metadata,
            "reason": request.reason,
            "max_depth": request.max_depth,
            "request_file_path": request.file_path,
            "request_symbol_name": request.symbol_name,
            "request_line_number": request.line_number,
            "original_context_id": context.context_id,
            "original_file_path": context.file_path,
            "relative_path": context.relative_path,
            "symbol_name": context.symbol_name,
            "symbol_type": context.symbol_type,
            "qualified_symbol": context.qualified_symbol,
            "calls": context.calls,
            "called_by": context.called_by,
            "imports": context.imports,
            "imported_by": context.imported_by,
            "config_keys": context.config_keys,
            "config_readers": context.config_readers,
            "relationship_types": relationship_types,
        }
        if graph_distance is not None:
            metadata["graph_distance"] = graph_distance
        if context.relevance_score is not None:
            metadata["graph_relevance_score"] = context.relevance_score
        if len(relationship_types) == 1:
            metadata.setdefault("relationship_type", relationship_types[0])
        metadata.setdefault("provider", type(self._code_graph_provider).__name__)

        return EvidenceCandidate(
            candidate_id=self._candidate_id(context, request),
            source_type=RetrievalEvidenceSourceType.CODE_GRAPH,
            retriever_name=self._retriever_name,
            content=self._content(context, relationship_types),
            file_path=context.relative_path,
            start_line=context.line_start,
            end_line=context.line_end,
            symbol_name=context.qualified_symbol,
            symbol_type=context.symbol_type,
            retrieval_query=query,
            metadata=metadata,
        )

    def _query_from_request(self, request: GraphExpansionRequest) -> str | None:
        parts = [
            value.strip()
            for value in (request.file_path, request.symbol_name)
            if value is not None and value.strip()
        ]
        if not parts:
            return None
        return " ".join(parts)

    def _content(
        self,
        context: CodeGraphContext,
        relationship_types: list[str],
    ) -> str:
        content = context.content.strip()
        if content:
            return content

        relationships = ", ".join(relationship_types) or "structural"
        return (
            f"Graph context: {context.qualified_symbol} in {context.relative_path} "
            f"has {relationships} relationships."
        )

    def _relationship_types(self, context: CodeGraphContext) -> list[str]:
        relationship_types: list[str] = []
        if context.calls:
            relationship_types.append("calls")
        if context.called_by:
            relationship_types.append("called_by")
        if context.imports:
            relationship_types.append("imports")
        if context.imported_by:
            relationship_types.append("imported_by")
        if context.config_keys:
            relationship_types.append("config_keys")
        if context.config_readers:
            relationship_types.append("config_readers")
        return relationship_types

    def _graph_distance(
        self,
        context: CodeGraphContext,
        request: GraphExpansionRequest,
    ) -> int | None:
        metadata_distance = context.metadata.get("graph_distance")
        if metadata_distance is not None:
            try:
                return int(metadata_distance)
            except ValueError:
                logger.warning(
                    "code graph expansion ignored invalid graph distance context_id=%s value=%s",
                    context.context_id,
                    metadata_distance,
                )

        requested_symbol = request.symbol_name
        if requested_symbol is None:
            return None
        if requested_symbol in {context.symbol_name, context.qualified_symbol}:
            return 0
        if any(
            requested_symbol in relationships
            for relationships in (
                context.calls,
                context.called_by,
                context.imports,
                context.imported_by,
                context.config_readers,
            )
        ):
            return 1
        return None

    def _candidate_id(
        self,
        context: CodeGraphContext,
        request: GraphExpansionRequest,
    ) -> str:
        identity = (
            f"code_graph:{context.context_id}:{request.file_path}:"
            f"{request.symbol_name}:{request.line_number}:{request.max_depth}"
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
        return f"EVID-GRAPH-{digest}"
