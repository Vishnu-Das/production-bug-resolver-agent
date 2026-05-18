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