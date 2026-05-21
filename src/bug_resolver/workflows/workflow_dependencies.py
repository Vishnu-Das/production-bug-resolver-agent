"""Shared workflow dependency setup helpers."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.config.settings import AppSettings
from bug_resolver.embeddings.openai_embedding_client import OpenAIEmbeddingClient
from bug_resolver.retrieval.code_file_loader import CodeFileLoader
from bug_resolver.retrieval.code_indexer import CodeIndexer
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore
from bug_resolver.retrieval.python_ast_code_chunker import PythonASTCodeChunker


async def load_or_build_code_index(
    *,
    settings: AppSettings,
    embedding_client: OpenAIEmbeddingClient,
) -> FAISSVectorStore:
    """Load an existing FAISS code index or build it from the target repository."""
    index_path = settings.faiss_index_dir / "code.index"
    metadata_path = settings.faiss_index_dir / "code_metadata.json"

    if index_path.exists() and metadata_path.exists():
        return FAISSVectorStore.load(
            index_path=index_path,
            metadata_path=metadata_path,
        )

    _ensure_path_exists(settings.target_repo_path, "target repository")

    indexer = CodeIndexer(
        file_loader=CodeFileLoader(settings.target_repo_path),
        chunker=PythonASTCodeChunker(),
        embedding_client=embedding_client,
    )
    vector_store = await indexer.build_index()
    vector_store.save(index_path=index_path, metadata_path=metadata_path)
    return vector_store


def _ensure_path_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Configured {label} path does not exist: {path}")
