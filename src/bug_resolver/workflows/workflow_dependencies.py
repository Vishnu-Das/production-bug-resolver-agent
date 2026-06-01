"""Shared workflow dependency setup helpers."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.config.settings import AppSettings
from bug_resolver.embeddings.openai_embedding_client import OpenAIEmbeddingClient
from bug_resolver.errors import ConfigurationError, RetrievalError
from bug_resolver.providers.code import CodeContextProvider
from bug_resolver.providers.graph import CodeGraphProvider
from bug_resolver.providers.knowledge import KnowledgeBaseProvider
from bug_resolver.providers.retrieval import (
    CodeGraphExpansionAdapter,
    KnowledgeSearchAdapter,
    LocalExactSearchProvider,
    LocalFileContextProvider,
    SemanticCodeSearchAdapter,
)
from bug_resolver.retrieval.code_file_loader import CodeFileLoader
from bug_resolver.retrieval.code_indexer import CodeIndexer
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore
from bug_resolver.retrieval.incident_driven_context_service import (
    IncidentDrivenContextService,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.retrieval.python_ast_code_chunker import PythonASTCodeChunker
from bug_resolver.utils.observability import get_logger


logger = get_logger(__name__)


def build_incident_driven_context_service(
    *,
    settings: AppSettings,
    code_context_provider: CodeContextProvider,
    code_graph_provider: CodeGraphProvider,
    knowledge_base_provider: KnowledgeBaseProvider,
) -> IncidentDrivenContextService:
    """Assemble the incident-driven retrieval pipeline from existing providers."""
    return IncidentDrivenContextService(
        ParallelContextRetriever(
            file_context_provider=LocalFileContextProvider(settings.target_repo_path),
            exact_search_provider=LocalExactSearchProvider(settings.target_repo_path),
            semantic_code_search_provider=SemanticCodeSearchAdapter(code_context_provider),
            code_graph_provider=CodeGraphExpansionAdapter(code_graph_provider),
            knowledge_search_provider=KnowledgeSearchAdapter(knowledge_base_provider),
        )
    )


async def load_or_build_code_index(
    *,
    settings: AppSettings,
    embedding_client: OpenAIEmbeddingClient,
) -> FAISSVectorStore:
    """Load an existing FAISS code index or build it from the target repository."""
    index_path = settings.faiss_index_dir / "code.index"
    metadata_path = settings.faiss_index_dir / "code_metadata.json"

    if index_path.exists() and metadata_path.exists():
        logger.info("loading existing code index index_path=%s metadata_path=%s", index_path, metadata_path)
        try:
            return FAISSVectorStore.load(
                index_path=index_path,
                metadata_path=metadata_path,
            )
        except Exception as exc:
            raise RetrievalError(
                "Failed to load existing FAISS code index.",
                component="code_index",
                context={
                    "index_path": index_path,
                    "metadata_path": metadata_path,
                },
            ) from exc

    _ensure_path_exists(settings.target_repo_path, "target repository")
    logger.info(
        "building code index target_repo_path=%s index_path=%s",
        settings.target_repo_path,
        index_path,
    )

    indexer = CodeIndexer(
        file_loader=CodeFileLoader(settings.target_repo_path),
        chunker=PythonASTCodeChunker(),
        embedding_client=embedding_client,
    )
    try:
        vector_store = await indexer.build_index()
        vector_store.save(index_path=index_path, metadata_path=metadata_path)
    except Exception as exc:
        raise RetrievalError(
            "Failed to build or save FAISS code index.",
            component="code_index",
            context={
                "target_repo_path": settings.target_repo_path,
                "index_path": index_path,
            },
        ) from exc
    logger.info("saved code index index_path=%s metadata_path=%s", index_path, metadata_path)
    return vector_store


def _ensure_path_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise ConfigurationError(
            f"Configured {label} path does not exist: {path}",
            component="settings",
            context={"path": path, "label": label},
        )
