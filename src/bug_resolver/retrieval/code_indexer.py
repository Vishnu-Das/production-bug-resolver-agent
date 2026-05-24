"""Build FAISS indexes from loaded and chunked target repository code."""

from __future__ import annotations

from typing import Any, Protocol

from bug_resolver.embeddings.base import EmbeddingClient
from bug_resolver.retrieval.code_chunker import CodeChunk
from bug_resolver.retrieval.code_file_loader import CodeFile, CodeFileLoader
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore
from bug_resolver.utils.observability import get_logger


logger = get_logger(__name__)


class CodeChunker(Protocol):
    """Chunker interface required by the code indexer."""

    def chunk_files(self, code_files: list[CodeFile]) -> list[CodeChunk]:
        ...


class CodeIndexer:
    """Create a searchable vector index from target repository code."""

    def __init__(
        self,
        file_loader: CodeFileLoader,
        chunker: CodeChunker,
        embedding_client: EmbeddingClient,
    ) -> None:
        self.file_loader = file_loader
        self.chunker = chunker
        self.embedding_client = embedding_client

    async def build_index(self) -> FAISSVectorStore:
        code_files = self.file_loader.load_files()
        chunks = self.chunker.chunk_files(code_files)
        logger.info("code index build loaded files=%s chunks=%s", len(code_files), len(chunks))

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
        logger.info("code index build finished vectors=%s dimension=%s", len(vectors), dimension)

        return vector_store

    def _chunk_to_metadata(self, chunk: CodeChunk) -> dict[str, Any]:
        metadata = {
            "item_id": chunk.chunk_id,
            "file_path": chunk.file_path,
            "relative_path": chunk.relative_path,
            "snippet": chunk.snippet,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "language": chunk.language,
            "metadata": chunk.metadata,
        }

        symbol_name = chunk.metadata.get("symbol_name")
        parent_symbol = chunk.metadata.get("parent_symbol")
        symbol_type = chunk.metadata.get("symbol_type")

        if symbol_name and symbol_type in {"class"}:
            metadata["class_name"] = symbol_name

        if symbol_name and symbol_type in {"function", "async_function"}:
            metadata["function_name"] = symbol_name

        if symbol_name and symbol_type in {"method", "async_method"}:
            metadata["class_name"] = parent_symbol
            metadata["function_name"] = symbol_name

        return metadata
