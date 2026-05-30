"""Tests for local incident-driven exact repository search."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.providers.retrieval import ExactSearchProvider, LocalExactSearchProvider
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    RetrievalEvidenceSourceType,
    RetrievalPlan,
    RetrievalQuery,
)


def _write_file(repo_path: Path, relative_path: str, content: str) -> Path:
    file_path = repo_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return file_path


def _query(value: str = "TypeError") -> RetrievalQuery:
    return RetrievalQuery(
        query=value,
        purpose="Find exact exception occurrence",
        priority=90,
        source_hint="exception_type",
    )


def test_local_exact_search_provider_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(LocalExactSearchProvider(tmp_path), ExactSearchProvider)


@pytest.mark.asyncio
async def test_exact_search_provider_finds_exact_term(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, "src/app.py", "raise TypeError('bad input')\n")

    candidates = await LocalExactSearchProvider(repo_path).search_exact([_query()])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_type == RetrievalEvidenceSourceType.CODE_EXACT
    assert candidate.retriever_name == "exact_search"
    assert candidate.file_path == "src/app.py"
    assert candidate.matched_terms == ["TypeError"]
    assert candidate.retrieval_query == "TypeError"
    assert "TypeError" in candidate.content
    assert candidate.metadata == {
        "purpose": "Find exact exception occurrence",
        "priority": 90,
        "source_hint": "exception_type",
        "match_line": 1,
    }


@pytest.mark.asyncio
async def test_exact_search_provider_is_case_insensitive(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, "src/app.py", "raise typeerror('bad input')\n")

    candidates = await LocalExactSearchProvider(repo_path).search_exact([_query()])

    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_exact_search_provider_includes_context_lines(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    lines = [f"line {line_number}" for line_number in range(1, 21)]
    lines[9] = "raise TypeError('bad input')"
    _write_file(repo_path, "src/app.py", "\n".join(lines))

    candidates = await LocalExactSearchProvider(
        repo_path,
        context_before_lines=2,
        context_after_lines=2,
    ).search_exact([_query()])

    assert candidates[0].start_line == 8
    assert candidates[0].end_line == 12
    assert "8: line 8" in candidates[0].content
    assert "10: raise TypeError('bad input')" in candidates[0].content
    assert "12: line 12" in candidates[0].content


@pytest.mark.asyncio
async def test_exact_search_provider_skips_excluded_directories(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, ".venv/file.py", "raise TypeError('ignore')\n")
    _write_file(repo_path, "src/app.py", "raise TypeError('include')\n")

    candidates = await LocalExactSearchProvider(repo_path).search_exact([_query()])

    assert [candidate.file_path for candidate in candidates] == ["src/app.py"]


@pytest.mark.asyncio
async def test_exact_search_provider_skips_large_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, "src/app.py", "x" * 100 + "TypeError\n")

    candidates = await LocalExactSearchProvider(
        repo_path,
        max_file_size_bytes=20,
    ).search_exact([_query()])

    assert candidates == []


@pytest.mark.asyncio
async def test_exact_search_provider_skips_binary_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    binary_file = repo_path / "src" / "artifact.bin"
    binary_file.parent.mkdir(parents=True)
    binary_file.write_bytes(b"\x00\x01TypeError\x02")

    candidates = await LocalExactSearchProvider(repo_path).search_exact([_query()])

    assert candidates == []


@pytest.mark.asyncio
async def test_exact_search_provider_deduplicates_results(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, "src/app.py", "raise TypeError('bad input')\n")

    candidates = await LocalExactSearchProvider(repo_path).search_exact([_query(), _query()])

    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_exact_search_provider_limits_results(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    for file_number in range(5):
        _write_file(
            repo_path,
            f"src/app_{file_number}.py",
            "raise TypeError('bad input')\n",
        )

    candidates = await LocalExactSearchProvider(
        repo_path,
        max_total_results=2,
    ).search_exact([_query()])

    assert len(candidates) == 2


@pytest.mark.asyncio
async def test_exact_search_provider_candidate_id_is_stable(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, "src/app.py", "raise TypeError('bad input')\n")
    provider = LocalExactSearchProvider(repo_path)

    first_candidates = await provider.search_exact([_query()])
    second_candidates = await provider.search_exact([_query()])

    assert first_candidates[0].candidate_id == second_candidates[0].candidate_id
    assert first_candidates[0].candidate_id.startswith("EVID-EXACT-")


@pytest.mark.asyncio
async def test_exact_search_provider_returns_empty_for_no_match(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, "src/app.py", "return 'ok'\n")

    candidates = await LocalExactSearchProvider(repo_path).search_exact([_query()])

    assert candidates == []


@pytest.mark.asyncio
async def test_exact_search_provider_runs_through_parallel_retriever(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _write_file(repo_path, "src/app.py", "raise TypeError('bad input')\n")
    retriever = ParallelContextRetriever(
        exact_search_provider=LocalExactSearchProvider(repo_path),
    )

    result = await retriever.retrieve(RetrievalPlan(exact_queries=[_query()]))

    assert len(result.candidates) == 1
    assert result.candidates[0].file_path == "src/app.py"
    assert result.failed_retrievers == []
