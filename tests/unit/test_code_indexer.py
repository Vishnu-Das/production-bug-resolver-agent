"""Tests for building code vector indexes from loaded chunks."""

import pytest

from bug_resolver.retrieval.code_chunker import SimpleCodeChunker
from bug_resolver.retrieval.code_file_loader import CodeFileLoader
from bug_resolver.retrieval.code_indexer import CodeIndexer


class FakeEmbeddingClient:
    async def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []

        for text in texts:
            if "search" in text.lower():
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([1.0, 0.0, 0.0])

        return vectors


class EmptyEmbeddingClient:
    async def embed_text(self, text: str) -> list[float]:
        return []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return []


@pytest.mark.asyncio
async def test_code_indexer_builds_faiss_index_from_code_files(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    app_file = repo_dir / "app.py"
    app_file.write_text(
        "def main():\n    print('hello')\n",
        encoding="utf-8",
    )

    search_file = repo_dir / "search.py"
    search_file.write_text(
        "def search():\n    return 'search result'\n",
        encoding="utf-8",
    )

    indexer = CodeIndexer(
        file_loader=CodeFileLoader(repo_path=repo_dir),
        chunker=SimpleCodeChunker(max_lines_per_chunk=10, overlap_lines=0),
        embedding_client=FakeEmbeddingClient(),
    )

    vector_store = await indexer.build_index()

    assert vector_store.size == 2

    results = vector_store.search([0.0, 1.0, 0.0], limit=1)

    assert len(results) == 1
    assert results[0].metadata["relative_path"] == "search.py"
    assert "def search" in results[0].metadata["snippet"]


@pytest.mark.asyncio
async def test_code_indexer_raises_when_no_code_chunks_exist(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    indexer = CodeIndexer(
        file_loader=CodeFileLoader(repo_path=repo_dir),
        chunker=SimpleCodeChunker(),
        embedding_client=FakeEmbeddingClient(),
    )

    with pytest.raises(ValueError, match="No code chunks found to index"):
        await indexer.build_index()


@pytest.mark.asyncio
async def test_code_indexer_raises_when_embedding_client_returns_no_vectors(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    app_file = repo_dir / "app.py"
    app_file.write_text(
        "def main():\n    print('hello')\n",
        encoding="utf-8",
    )

    indexer = CodeIndexer(
        file_loader=CodeFileLoader(repo_path=repo_dir),
        chunker=SimpleCodeChunker(),
        embedding_client=EmptyEmbeddingClient(),
    )

    with pytest.raises(ValueError, match="Embedding client returned no vectors"):
        await indexer.build_index()
