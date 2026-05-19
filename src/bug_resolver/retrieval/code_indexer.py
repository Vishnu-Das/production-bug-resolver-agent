"""Build FAISS indexes from loaded and chunked target repository code."""

from __future__ import annotations

from typing import Any

from bug_resolver.embeddings.base import EmbeddingClient
from bug_resolver.retrieval.code_chunker import CodeChunk, SimpleCodeChunker
from bug_resolver.retrieval.code_file_loader import CodeFileLoader
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore


class CodeIndexer:
    """Create a searchable vector index from target repository code."""

    def __init__(
        self,
        file_loader: CodeFileLoader,
        chunker: SimpleCodeChunker,
        embedding_client: EmbeddingClient,
    ) -> None:
        self.file_loader = file_loader
        self.chunker = chunker
        self.embedding_client = embedding_client

    async def build_index(self) -> FAISSVectorStore:
        code_files = self.file_loader.load_files()
        chunks = self.chunker.chunk_files(code_files)

        if not chunks:
            raise ValueError("No code chunks found to index")

        snippets = [chunk.snippet for chunk in chunks]
        vectors = await self.embedding_client.embed_texts(snippets)

        if not vectors:
            raise ValueError("Embedding client returned no vectors")

        dimension = len(vectors[0])
        vector_store = FAISSVectorStore(dimension=dimension)

        vector_store.add(
            vectors=vectors,
            metadata=[self._chunk_to_metadata(chunk) for chunk in chunks],
        )

        return vector_store

    def _chunk_to_metadata(self, chunk: CodeChunk) -> dict[str, Any]:
        return {
            "item_id": chunk.chunk_id,
            "file_path": chunk.file_path,
            "relative_path": chunk.relative_path,
            "snippet": chunk.snippet,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "language": chunk.language,
            "metadata": chunk.metadata,
        }
