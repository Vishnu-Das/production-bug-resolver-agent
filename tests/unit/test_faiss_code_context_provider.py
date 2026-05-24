"""Tests for semantic code context retrieval from FAISS metadata."""

import pytest

from bug_resolver.providers.code.faiss_code_context_provider import (
    FAISSCodeContextProvider,
)
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore


class FakeEmbeddingClient:
    async def embed_text(self, text: str) -> list[float]:
        if "search" in text.lower():
            return [0.0, 1.0, 0.0]

        return [1.0, 0.0, 0.0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(text) for text in texts]


def build_vector_store() -> FAISSVectorStore:
    store = FAISSVectorStore(dimension=3)

    store.add(
        vectors=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        metadata=[
            {
                "item_id": "app.py:1-3",
                "file_path": "/repo/app.py",
                "relative_path": "app.py",
                "snippet": "def main():\n    print('hello')",
                "line_start": 1,
                "line_end": 3,
                "language": "python",
                "metadata": {
                    "extension": ".py",
                    "chunk_number": "1",
                },
            },
            {
                "item_id": "search.py:1-2",
                "file_path": "/repo/search.py",
                "relative_path": "search.py",
                "snippet": "def search():\n    return 'result'",
                "line_start": 1,
                "line_end": 2,
                "language": "python",
                "metadata": {
                    "extension": ".py",
                    "chunk_number": "1",
                },
            },
        ],
    )

    return store


def build_vector_store_with_deprecated_match() -> FAISSVectorStore:
    store = FAISSVectorStore(dimension=3)
    store.add(
        vectors=[
            [0.0, 1.0, 0.0],
            [0.0, 0.9, 0.1],
        ],
        metadata=[
            {
                "item_id": "src/obsolette_rag.py:1-20",
                "file_path": "/repo/src/obsolette_rag.py",
                "snippet": "deprecated implementation",
                "line_start": 1,
                "line_end": 20,
            },
            {
                "item_id": "src/rag/service.py:1-20",
                "file_path": "/repo/src/rag/service.py",
                "snippet": "active implementation",
                "line_start": 1,
                "line_end": 20,
            },
        ],
    )
    return store


def build_vector_store_with_noisy_test_match() -> FAISSVectorStore:
    store = FAISSVectorStore(dimension=3)
    store.add(
        vectors=[
            [0.0, 1.0, 0.0],
            [0.0, 0.96, 0.28],
        ],
        metadata=[
            {
                "item_id": "tests/rag/test_service.py:1-40",
                "file_path": "/repo/tests/rag/test_service.py",
                "snippet": "def test_retrieval_service(): pass",
                "line_start": 1,
                "line_end": 40,
            },
            {
                "item_id": "src/rag/service.py:1-40",
                "file_path": "/repo/src/rag/service.py",
                "snippet": "def retrieve_documents(): pass",
                "line_start": 1,
                "line_end": 40,
            },
        ],
    )
    return store


def build_vector_store_with_deep_implementation_match() -> FAISSVectorStore:
    store = FAISSVectorStore(dimension=3)
    vectors = [[0.0, 1.0, 0.0] for _ in range(12)]
    vectors.append([0.0, 0.8, 0.6])
    metadata = [
        {
            "item_id": f"tests/rag/test_service.py:test_case_{index}",
            "file_path": "/repo/tests/rag/test_service.py",
            "snippet": "def test_stream_response_uses_router_selected_strategy(): pass",
            "line_start": index + 1,
            "line_end": index + 1,
        }
        for index in range(12)
    ]
    metadata.append(
        {
            "item_id": "src/services/upload_service.py:handle_file_upload",
            "file_path": "/repo/src/services/upload_service.py",
            "snippet": (
                "def handle_file_upload(): "
                "content_hash = hashlib.sha256(file_bytes).hexdigest(); "
                "st.session_state.processed_uploads.add(filename)"
            ),
            "line_start": 1,
            "line_end": 20,
            "function_name": "handle_file_upload",
            "metadata": {"qualified_symbol": "handle_file_upload"},
        }
    )
    store.add(vectors=vectors, metadata=metadata)
    return store


def build_vector_store_for_bm25_frequency() -> FAISSVectorStore:
    store = FAISSVectorStore(dimension=3)
    store.add(
        vectors=[
            [0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        metadata=[
            {
                "item_id": "src/services/generic.py:handler",
                "file_path": "/repo/src/services/generic.py",
                "snippet": "def handler(): upload once",
                "line_start": 1,
                "line_end": 10,
                "function_name": "handler",
            },
            {
                "item_id": "src/services/upload.py:handle_upload",
                "file_path": "/repo/src/services/upload.py",
                "snippet": "def handle_upload(): upload upload upload content_hash",
                "line_start": 1,
                "line_end": 10,
                "function_name": "handle_upload",
            },
        ],
    )
    return store


@pytest.mark.asyncio
async def test_faiss_code_context_provider_returns_matching_context():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(["search function"], limit=1)

    assert len(results) == 1

    result = results[0]

    assert result.context_id == "search.py:1-2"
    assert result.file_path == "/repo/search.py"
    assert result.snippet == "def search():\n    return 'result'"
    assert result.line_start == 1
    assert result.line_end == 2
    assert result.retrieval_query == "search function"
    assert result.relevance_score is not None
    assert result.relevance_score > 0.99
    assert result.metadata["provider"] == "faiss_code_context"
    assert result.metadata["relative_path"] == "search.py"
    assert result.metadata["language"] == "python"
    assert result.metadata["extension"] == ".py"


@pytest.mark.asyncio
async def test_faiss_code_context_provider_returns_empty_list_for_empty_queries():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(["", "   "], limit=5)

    assert results == []


@pytest.mark.asyncio
async def test_faiss_code_context_provider_rejects_invalid_limit():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store(),
        embedding_client=FakeEmbeddingClient(),
    )

    with pytest.raises(ValueError, match="limit must be greater than 0"):
        await provider.search_code(["search"], limit=0)


@pytest.mark.asyncio
async def test_faiss_code_context_provider_deduplicates_results():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(
        [
            "search function",
            "search result",
        ],
        limit=5,
    )

    context_ids = [result.context_id for result in results]

    assert len(context_ids) == len(set(context_ids))
    assert "search.py:1-2" in context_ids


@pytest.mark.asyncio
async def test_faiss_code_context_provider_respects_limit():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(["search"], limit=1)

    assert len(results) == 1


@pytest.mark.asyncio
async def test_faiss_code_context_provider_filters_deprecated_paths():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store_with_deprecated_match(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(["search"], limit=2)

    assert [result.context_id for result in results] == ["src/rag/service.py:1-20"]


@pytest.mark.asyncio
async def test_faiss_code_context_provider_returns_ranked_top_k_results():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store_with_noisy_test_match(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(["search retrieval service"], limit=1)

    assert [result.context_id for result in results] == ["src/rag/service.py:1-40"]


@pytest.mark.asyncio
async def test_faiss_code_context_provider_retrieves_deeper_primary_implementation_candidates():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store_with_deep_implementation_match(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(
        ["search duplicate upload content_hash processed_uploads handler"],
        limit=3,
    )

    assert [result.context_id for result in results] == [
        "src/services/upload_service.py:handle_file_upload"
    ]


@pytest.mark.asyncio
async def test_faiss_code_context_provider_exact_lexical_match_beats_noisy_semantic_test():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store_with_deep_implementation_match(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(["processed_uploads content_hash"], limit=1)

    assert [result.context_id for result in results] == [
        "src/services/upload_service.py:handle_file_upload"
    ]


@pytest.mark.asyncio
async def test_faiss_code_context_provider_bm25_lexical_search_uses_term_frequency():
    provider = FAISSCodeContextProvider(
        vector_store=build_vector_store_for_bm25_frequency(),
        embedding_client=FakeEmbeddingClient(),
    )

    results = await provider.search_code(["upload"], limit=1)

    assert [result.context_id for result in results] == [
        "src/services/upload.py:handle_upload"
    ]
