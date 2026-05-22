"""Tests for local AST-derived code graph retrieval."""

from pathlib import Path

import pytest

from bug_resolver.providers.graph import PythonASTCodeGraphProvider
from bug_resolver.schemas import EvidenceSourceType


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.asyncio
async def test_python_ast_code_graph_provider_extracts_calls_and_config_keys(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "src" / "reranker.py",
        """
import os


def load_reranker():
    return os.getenv("RERANKING_MODEL_NAME")


def rerank_documents(documents):
    model_name = load_reranker()
    return documents if model_name else documents
""".strip(),
    )

    provider = PythonASTCodeGraphProvider(tmp_path)

    contexts = await provider.search_graph(
        ["who calls load_reranker RERANKING_MODEL_NAME"],
        limit=5,
    )

    assert {context.qualified_symbol for context in contexts} >= {
        "load_reranker",
        "rerank_documents",
    }

    load_context = next(
        context for context in contexts if context.qualified_symbol == "load_reranker"
    )
    rerank_context = next(
        context for context in contexts if context.qualified_symbol == "rerank_documents"
    )

    assert load_context.config_keys == ["RERANKING_MODEL_NAME"]
    assert "rerank_documents" in load_context.called_by
    assert "load_reranker" in rerank_context.calls
    assert "RERANKING_MODEL_NAME" in rerank_context.config_keys
    assert rerank_context.config_readers == ["load_reranker"]


@pytest.mark.asyncio
async def test_python_ast_code_graph_provider_extracts_class_methods(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "src" / "upload.py",
        """
class UploadService:
    def handle_file_upload(self, file):
        return self._deduplicate(file)

    def _deduplicate(self, file):
        return file
""".strip(),
    )

    provider = PythonASTCodeGraphProvider(tmp_path)

    contexts = await provider.search_graph(
        ["UploadService handle_file_upload deduplicate"],
        limit=5,
    )

    assert {context.qualified_symbol for context in contexts} >= {
        "UploadService",
        "UploadService.handle_file_upload",
        "UploadService._deduplicate",
    }

    upload_context = next(
        context
        for context in contexts
        if context.qualified_symbol == "UploadService.handle_file_upload"
    )
    assert upload_context.symbol_type == "method"
    assert "self._deduplicate" in upload_context.calls


@pytest.mark.asyncio
async def test_python_ast_code_graph_provider_converts_context_to_graph_evidence(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "src" / "settings.py",
        """
def load_config():
    return "ok"
""".strip(),
    )
    provider = PythonASTCodeGraphProvider(tmp_path)

    contexts = await provider.search_graph(["load_config"], limit=1)
    evidence = contexts[0].to_evidence_item()

    assert evidence.source_type == EvidenceSourceType.GRAPH
    assert evidence.evidence_id == "graph-src/settings.py:load_config"
    assert evidence.metadata["qualified_symbol"] == "load_config"
    assert evidence.metadata["provider"] == "python_ast_code_graph"


@pytest.mark.asyncio
async def test_python_ast_code_graph_provider_includes_config_reader_metadata(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "src" / "reranker.py",
        """
import os


def load_reranker():
    return CrossEncoder(RERANKING_MODEL_NAME)


reranker_model = load_reranker()


def rerank_documents_with_scores(documents):
    scores = reranker_model.predict(documents)
    return scores
""".strip(),
    )
    provider = PythonASTCodeGraphProvider(tmp_path)

    contexts = await provider.search_graph(
        ["rerank_documents_with_scores RERANKING_MODEL_NAME"],
        limit=5,
    )
    context = next(
        item
        for item in contexts
        if item.qualified_symbol == "rerank_documents_with_scores"
    )
    evidence = context.to_evidence_item()

    assert context.config_readers == ["load_reranker"]
    assert evidence.metadata["config_readers"] == "load_reranker"
