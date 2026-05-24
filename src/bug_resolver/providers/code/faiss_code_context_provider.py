"""FAISS-backed code context provider for semantic source search."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import log
from typing import Any

from bug_resolver.embeddings.base import EmbeddingClient
from bug_resolver.providers.code.base import CodeContextProvider
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore, VectorSearchResult
from bug_resolver.rules.code_context_ranking_rules import CodeContextRankingRules
from bug_resolver.schemas.code_context import CodeContext
from bug_resolver.utils.observability import get_logger, log_debug_payload, traceable


logger = get_logger(__name__)


@dataclass(frozen=True)
class BM25Document:
    """Tokenized lexical-search document backed by vector-store metadata."""

    metadata: dict[str, Any]
    tokens: tuple[str, ...]
    token_counts: Counter[str]
    source_text: str
    path_text: str
    symbol_text: str


class FAISSCodeContextProvider(CodeContextProvider):
    """Retrieve source-code evidence from a FAISS index of repository chunks."""

    def __init__(
        self,
        vector_store: FAISSVectorStore,
        embedding_client: EmbeddingClient,
        ranking_rules: CodeContextRankingRules | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.ranking_rules = ranking_rules or CodeContextRankingRules()
        self._bm25_documents: list[BM25Document] | None = None

    @traceable(name="code_context.search", run_type="retriever")
    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        cleaned_queries = [query.strip() for query in queries if query.strip()]

        if not cleaned_queries:
            return []

        logger.info(
            "code search started query_count=%s limit=%s candidate_limit_per_query=%s",
            len(cleaned_queries),
            limit,
            max(limit * 10, 50),
        )
        log_debug_payload(logger, "code search queries", payload=cleaned_queries)

        contexts_by_id: dict[str, CodeContext] = {}

        per_query_limit = max(limit * 10, 50)

        for query in cleaned_queries:
            query_vector = await self.embedding_client.embed_text(query)

            search_results = self.vector_store.search(
                query_vector=query_vector,
                limit=per_query_limit,
            )
            lexical_results = self._lexical_search(query, limit=per_query_limit)
            search_results = self._merge_search_results(search_results, lexical_results)
            logger.debug(
                "code search returned query=%s candidate_count=%s lexical_count=%s",
                query[:120],
                len(search_results),
                len(lexical_results),
            )

            for search_result in search_results:
                if self._is_deprecated_path(search_result.metadata.get("file_path")):
                    continue

                context = self._to_code_context(
                    search_result=search_result,
                    retrieval_query=query,
                )

                existing_context = contexts_by_id.get(context.context_id)

                if existing_context is None:
                    contexts_by_id[context.context_id] = context
                    continue

                existing_score = existing_context.relevance_score or 0.0
                new_score = context.relevance_score or 0.0

                if new_score > existing_score:
                    contexts_by_id[context.context_id] = context

        ranked_contexts = self.ranking_rules.rank_contexts(
            list(contexts_by_id.values()),
            queries=cleaned_queries,
            limit=limit,
            mode="implementation",
        )
        logger.info(
            "code search finished unique_candidates=%s returned=%s",
            len(contexts_by_id),
            len(ranked_contexts),
        )
        log_debug_payload(
            logger,
            "code search returned contexts",
            payload=[
                {
                    "context_id": context.context_id,
                    "file_path": context.file_path,
                    "symbol": context.metadata.get("qualified_symbol")
                    or context.function_name
                    or context.class_name,
                    "score": context.relevance_score,
                    "query": context.retrieval_query,
                }
                for context in ranked_contexts
            ],
        )
        return ranked_contexts

    def _lexical_search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[VectorSearchResult]:
        query_tokens = self._tokenize_for_bm25(query)
        exact_identifiers = self._exact_identifiers(query)
        if not query_tokens and not exact_identifiers:
            return []

        documents = self._get_bm25_documents()
        if not documents:
            return []

        bm25_scores = self._bm25_scores(query_tokens=query_tokens, documents=documents)
        max_bm25_score = max(bm25_scores, default=0.0)
        scored_results: list[VectorSearchResult] = []

        for document, bm25_score in zip(documents, bm25_scores, strict=True):
            score = self._normalized_bm25_score(
                bm25_score=bm25_score,
                max_bm25_score=max_bm25_score,
            )
            score += self._exact_identifier_boost(
                document=document,
                exact_identifiers=exact_identifiers,
            )
            if score <= 0:
                continue

            scored_results.append(
                VectorSearchResult(
                    item_id=str(document.metadata["item_id"]),
                    score=min(score, 1.0),
                    metadata=document.metadata,
                )
            )

        scored_results.sort(key=lambda result: (-result.score, result.item_id))
        return scored_results[:limit]

    def _get_bm25_documents(self) -> list[BM25Document]:
        if self._bm25_documents is None:
            self._bm25_documents = [
                self._to_bm25_document(metadata)
                for metadata in self.vector_store.metadata_by_position
            ]

        return self._bm25_documents

    def _to_bm25_document(self, metadata: dict[str, Any]) -> BM25Document:
        path_text = str(
            metadata.get("file_path")
            or metadata.get("relative_path")
            or ""
        )
        snippet = str(metadata.get("snippet") or "")
        symbol_text = " ".join(
            str(metadata.get(key) or "")
            for key in ("class_name", "function_name", "qualified_symbol")
        )
        metadata_text = self._metadata_text(metadata.get("metadata"))
        source_text = " ".join(
            [
                path_text,
                path_text,
                symbol_text,
                symbol_text,
                symbol_text,
                metadata_text,
                snippet,
            ]
        )
        tokens = tuple(self._tokenize_for_bm25(source_text))

        return BM25Document(
            metadata=metadata,
            tokens=tokens,
            token_counts=Counter(tokens),
            source_text=source_text,
            path_text=path_text,
            symbol_text=symbol_text,
        )

    def _bm25_scores(
        self,
        *,
        query_tokens: list[str],
        documents: list[BM25Document],
    ) -> list[float]:
        document_count = len(documents)
        average_document_length = sum(len(document.tokens) for document in documents) / max(
            document_count,
            1,
        )
        document_frequency = Counter(
            token
            for token in set(query_tokens)
            for document in documents
            if token in document.token_counts
        )
        k1 = 1.5
        b = 0.75
        scores: list[float] = []

        for document in documents:
            document_length = len(document.tokens)
            score = 0.0
            for query_token in query_tokens:
                term_frequency = document.token_counts.get(query_token, 0)
                if term_frequency == 0:
                    continue

                matching_documents = document_frequency[query_token]
                idf = log(
                    1
                    + (document_count - matching_documents + 0.5)
                    / (matching_documents + 0.5)
                )
                denominator = term_frequency + k1 * (
                    1 - b + b * document_length / max(average_document_length, 1)
                )
                score += idf * (term_frequency * (k1 + 1)) / denominator

            scores.append(score)

        return scores

    def _normalized_bm25_score(
        self,
        *,
        bm25_score: float,
        max_bm25_score: float,
    ) -> float:
        if bm25_score <= 0 or max_bm25_score <= 0:
            return 0.0

        return (bm25_score / max_bm25_score) * 0.85

    def _exact_identifier_boost(
        self,
        *,
        document: BM25Document,
        exact_identifiers: set[str],
    ) -> float:
        boost = 0.0
        source_text_lower = document.source_text.lower()
        path_text_lower = document.path_text.lower()
        symbol_text_lower = document.symbol_text.lower()
        for identifier in exact_identifiers:
            identifier_lower = identifier.lower()
            if identifier_lower in source_text_lower:
                boost += 0.20
                if identifier_lower in path_text_lower:
                    boost += 0.10
                if identifier_lower in symbol_text_lower:
                    boost += 0.15

        return boost

    def _tokenize_for_bm25(self, value: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9_]+", value.lower())
        split_tokens = [
            part
            for token in tokens
            for part in token.split("_")
            if part
        ]
        return tokens + split_tokens

    def _merge_search_results(
        self,
        semantic_results: list[VectorSearchResult],
        lexical_results: list[VectorSearchResult],
    ) -> list[VectorSearchResult]:
        results_by_id: dict[str, VectorSearchResult] = {}

        for result in [*semantic_results, *lexical_results]:
            existing = results_by_id.get(result.item_id)
            if existing is None or result.score > existing.score:
                results_by_id[result.item_id] = result

        return sorted(
            results_by_id.values(),
            key=lambda result: (-result.score, result.item_id),
        )

    def _exact_identifiers(self, value: str) -> set[str]:
        identifiers = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", value))
        identifiers.update(
            token
            for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", value)
            if "_" in token
        )
        identifiers.update(
            re.findall(
                r"\b[A-Za-z0-9_./\\-]+\.(?:py|toml|json|yaml|yml|env|ini|cfg)\b",
                value,
            )
        )
        identifiers.update(
            re.findall(r"\b[A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b", value)
        )
        return identifiers

    def _metadata_text(self, metadata: object) -> str:
        if isinstance(metadata, dict):
            return " ".join(str(value) for value in metadata.values())

        return str(metadata or "")

    def _is_deprecated_path(self, file_path: object) -> bool:
        if file_path is None:
            return False

        normalized_path = str(file_path).replace("\\", "/").lower()
        return any(marker in normalized_path for marker in ("obsolete", "obsolette", "deprecated"))

    def _to_code_context(
        self,
        search_result: VectorSearchResult,
        retrieval_query: str,
    ) -> CodeContext:
        metadata = search_result.metadata

        return CodeContext(
            context_id=search_result.item_id,
            file_path=str(metadata["file_path"]),
            snippet=str(metadata["snippet"]),
            line_start=self._optional_int(metadata.get("line_start")),
            line_end=self._optional_int(metadata.get("line_end")),
            class_name=self._optional_str(metadata.get("class_name")),
            function_name=self._optional_str(metadata.get("function_name")),
            retrieval_query=retrieval_query,
            relevance_score=self._normalize_score(search_result.score),
            metadata=self._to_string_metadata(metadata),
        )

    def _normalize_score(self, score: float) -> float:
        return max(0.0, min(score, 1.0))

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None

        return int(value)

    def _optional_str(self, value: Any) -> str | None:
        if value is None:
            return None

        return str(value)

    def _to_string_metadata(self, metadata: dict[str, Any]) -> dict[str, str]:
        excluded_keys = {
            "item_id",
            "file_path",
            "snippet",
            "line_start",
            "line_end",
            "class_name",
            "function_name",
        }

        string_metadata: dict[str, str] = {}

        for key, value in metadata.items():
            if key in excluded_keys:
                continue

            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    string_metadata[str(nested_key)] = str(nested_value)
                continue

            string_metadata[str(key)] = str(value)

        string_metadata["provider"] = "faiss_code_context"

        return string_metadata
