"""Tests for local incident-driven file context retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.providers.retrieval import FileContextProvider, LocalFileContextProvider
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import FileContextRequest, RetrievalEvidenceSourceType, RetrievalPlan


def _write_numbered_file(repo_path: Path, *, line_count: int = 100) -> Path:
    source_file = repo_path / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "\n".join(f"line {line_number}" for line_number in range(1, line_count + 1)),
        encoding="utf-8",
    )
    return source_file


def _request(
    *,
    file_path: str = "src/app.py",
    line_number: int | None = 50,
    before_lines: int = 5,
    after_lines: int = 5,
) -> FileContextRequest:
    return FileContextRequest(
        file_path=file_path,
        line_number=line_number,
        before_lines=before_lines,
        after_lines=after_lines,
        reason="Read source around incident location",
    )


def test_local_file_context_provider_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(LocalFileContextProvider(tmp_path), FileContextProvider)


@pytest.mark.asyncio
async def test_file_context_provider_reads_context_around_line(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_numbered_file(repo_path)

    candidates = await LocalFileContextProvider(repo_path).read_context([_request()])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_type == RetrievalEvidenceSourceType.FILE_CONTEXT
    assert candidate.retriever_name == "file_context"
    assert candidate.file_path == "src/app.py"
    assert candidate.start_line == 45
    assert candidate.end_line == 55
    assert "50: line 50" in candidate.content
    assert candidate.metadata == {
        "requested_line_number": 50,
        "before_lines": 5,
        "after_lines": 5,
        "reason": "Read source around incident location",
    }


@pytest.mark.asyncio
async def test_file_context_provider_clamps_start_and_end(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_numbered_file(repo_path, line_count=20)
    provider = LocalFileContextProvider(repo_path)

    candidates = await provider.read_context(
        [
            _request(line_number=2, before_lines=10, after_lines=10),
            _request(line_number=19, before_lines=10, after_lines=10),
        ]
    )

    assert candidates[0].start_line == 1
    assert candidates[0].end_line == 12
    assert candidates[1].start_line == 9
    assert candidates[1].end_line == 20


@pytest.mark.asyncio
async def test_file_context_provider_reads_first_chunk_when_no_line_number(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    _write_numbered_file(repo_path, line_count=150)

    candidates = await LocalFileContextProvider(repo_path).read_context(
        [_request(line_number=None)]
    )

    assert len(candidates) == 1
    assert candidates[0].start_line == 1
    assert candidates[0].end_line == 120
    assert "1: line 1" in candidates[0].content
    assert "120: line 120" in candidates[0].content
    assert "121: line 121" not in candidates[0].content


@pytest.mark.asyncio
async def test_file_context_provider_skips_missing_file(tmp_path: Path) -> None:
    candidates = await LocalFileContextProvider(tmp_path / "repo").read_context(
        [_request(file_path="src/missing.py")]
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_file_context_provider_blocks_path_traversal(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (tmp_path / "outside.py").write_text("SECRET = True\n", encoding="utf-8")

    candidates = await LocalFileContextProvider(repo_path).read_context(
        [_request(file_path="../outside.py")]
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_file_context_provider_allows_absolute_path_inside_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    source_file = _write_numbered_file(repo_path)

    candidates = await LocalFileContextProvider(repo_path).read_context(
        [_request(file_path=str(source_file))]
    )

    assert len(candidates) == 1
    assert candidates[0].file_path == "src/app.py"


@pytest.mark.asyncio
async def test_file_context_provider_deduplicates_requests(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_numbered_file(repo_path)
    request = _request()

    candidates = await LocalFileContextProvider(repo_path).read_context([request, request])

    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_file_context_provider_candidate_id_is_stable(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_numbered_file(repo_path)
    provider = LocalFileContextProvider(repo_path)

    first_candidates = await provider.read_context([_request()])
    second_candidates = await provider.read_context([_request()])

    assert first_candidates[0].candidate_id == second_candidates[0].candidate_id
    assert first_candidates[0].candidate_id.startswith("EVID-FILE-")


@pytest.mark.asyncio
async def test_file_context_provider_handles_invalid_utf8(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    source_file = repo_path / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"valid\ninvalid: \xff\n")

    candidates = await LocalFileContextProvider(repo_path).read_context(
        [_request(line_number=None)]
    )

    assert len(candidates) == 1
    assert "invalid: \ufffd" in candidates[0].content


@pytest.mark.asyncio
async def test_file_context_provider_runs_through_parallel_retriever(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_numbered_file(repo_path)
    retriever = ParallelContextRetriever(
        file_context_provider=LocalFileContextProvider(repo_path),
    )

    result = await retriever.retrieve(RetrievalPlan(file_context_requests=[_request()]))

    assert len(result.candidates) == 1
    assert result.candidates[0].file_path == "src/app.py"
    assert result.failed_retrievers == []
