from __future__ import annotations

from typing import Any

from bug_resolver.embeddings.base import EmbeddingClient
from bug_resolver.providers.code.base import CodeContextProvider
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore, VectorSearchResult
from bug_resolver.schemas.code_context import CodeContext


class FAISSCodeContextProvider(CodeContextProvider):
    def __init__(
        self,
        vector_store: FAISSVectorStore,
        embedding_client: EmbeddingClient,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_client = embedding_client

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

        contexts_by_id: dict[str, CodeContext] = {}

        per_query_limit = max(limit, 1)

        for query in cleaned_queries:
            query_vector = await self.embedding_client.embed_text(query)

            search_results = self.vector_store.search(
                query_vector=query_vector,
                limit=per_query_limit * 3,
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

        contexts = sorted(
            contexts_by_id.values(),
            key=lambda context: context.relevance_score or 0.0,
            reverse=True,
        )

        return contexts[:limit]

    def _is_deprecated_path(self, file_path: object) -> bool:
        if file_path is None:
            return False

        normalized_path = str(file_path).replace("\\", "/").lower()
        return any(
            marker in normalized_path
            for marker in ("obsolete", "obsolette", "deprecated")
        )

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
