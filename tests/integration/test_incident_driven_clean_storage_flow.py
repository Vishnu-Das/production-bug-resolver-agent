"""Clean-storage regressions for local incident-driven retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.config.settings import AppSettings
from bug_resolver.providers.reports import FileReportStore
from bug_resolver.providers.retrieval import (
    LocalExactSearchProvider,
    LocalFileContextProvider,
)
from bug_resolver.retrieval.incident_driven_context_service import (
    IncidentDrivenContextService,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    EvidenceCandidate,
    GraphExpansionRequest,
    RCAReport,
    RetrievalQuery,
)
from bug_resolver.workflows.workflow_dependencies import load_or_build_code_index


class FakeEmbeddingClient:
    """Return stable local vectors without requiring OpenAI."""

    async def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FailingOptionalRetrievalProvider:
    """Represent optional indexes that are unavailable in a clean environment."""

    async def search_semantic_code(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        raise RuntimeError("semantic index unavailable")

    async def expand_context(
        self,
        requests: list[GraphExpansionRequest],
    ) -> list[EvidenceCandidate]:
        raise RuntimeError("graph index unavailable")

    async def search_knowledge(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        raise RuntimeError("knowledge index unavailable")


def _write_file(repo_path: Path, relative_path: str, content: str) -> None:
    file_path = repo_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _source_with_failure_at_line_42() -> str:
    lines = ["# fixture padding"] * 50
    lines[39] = "def handle_request(payload):"
    lines[40] = "    if payload is None:"
    lines[41] = '        raise TypeError("payload cannot be None")'
    lines[42] = "    return payload"
    return "\n".join(lines) + "\n"


@pytest.mark.asyncio
async def test_missing_faiss_storage_is_created_when_code_index_is_built(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "target_repo"
    storage_path = tmp_path / "generated" / "storage"
    _write_file(repo_path, "src/app.py", "def handle_request():\n    return 'ok'\n")
    settings = AppSettings(
        target_repo_path=repo_path,
        faiss_index_dir=storage_path / "faiss",
    )

    assert not storage_path.exists()

    vector_store = await load_or_build_code_index(
        settings=settings,
        embedding_client=FakeEmbeddingClient(),  # type: ignore[arg-type]
    )

    assert vector_store.size > 0
    assert (storage_path / "faiss" / "code.index").exists()
    assert (storage_path / "faiss" / "code_metadata.json").exists()


@pytest.mark.asyncio
async def test_file_and_exact_retrieval_survive_missing_optional_storage(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "target_repo"
    storage_path = tmp_path / "generated" / "storage"
    reports_path = tmp_path / "generated" / "reports"
    _write_file(repo_path, "src/app.py", _source_with_failure_at_line_42())
    optional_provider = FailingOptionalRetrievalProvider()
    service = IncidentDrivenContextService(
        ParallelContextRetriever(
            file_context_provider=LocalFileContextProvider(repo_path),
            exact_search_provider=LocalExactSearchProvider(repo_path),
            semantic_code_search_provider=optional_provider,
            code_graph_provider=optional_provider,
            knowledge_search_provider=optional_provider,
        )
    )

    assert not storage_path.exists()
    assert not reports_path.exists()

    result = await service.build_context(
        incident_id="INC-CLEAN-STORAGE",
        summary="Request fails when payload is empty",
        log_texts=[
            "\n".join(
                [
                    "Traceback (most recent call last):",
                    '  File "src/app.py", line 42, in handle_request',
                    '    raise TypeError("payload cannot be None")',
                    "TypeError: payload cannot be None",
                ]
            )
        ],
    )

    assert result.evaluation.selected_evidence
    assert result.evaluation.has_direct_code_evidence is True
    assert result.evaluation.sufficient_for_rca is True
    assert result.evaluation.selected_evidence[0].candidate.file_path == "src/app.py"
    assert result.evaluation.selected_evidence[0].score.reasons
    assert result.failed_retrievers == [
        "semantic_code_search",
        "code_graph_expansion",
        "knowledge_search",
    ]
    assert any("semantic index unavailable" in warning for warning in result.retrieval_warnings)
    assert any("graph index unavailable" in warning for warning in result.retrieval_warnings)
    assert any("knowledge index unavailable" in warning for warning in result.retrieval_warnings)
    assert not storage_path.exists()
    assert not reports_path.exists()

    report = RCAReport(
        report_id="RCA-CLEAN-STORAGE",
        incident_id="INC-CLEAN-STORAGE",
        title="RCA for request failure",
        incident_summary="The request failed for an empty payload.",
        root_cause="The handler raises TypeError for an empty payload.",
        technical_explanation="File context and exact search identify the failing line.",
        evidence_ids=[
            result.evaluation.selected_evidence[0].candidate.candidate_id,
        ],
        confidence_score=0.8,
        confidence_reason="Direct source context matches the stack trace.",
    )
    written_paths = await FileReportStore(reports_path).save_report(report)

    assert reports_path.exists()
    assert all(path.exists() for path in written_paths)
    assert not storage_path.exists()
