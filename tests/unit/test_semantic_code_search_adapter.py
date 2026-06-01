"""Tests for adapting existing semantic code search into retrieval candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bug_resolver.providers.retrieval import (
    SemanticCodeSearchAdapter,
    SemanticCodeSearchProvider,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    CodeContext,
    RetrievalEvidenceSourceType,
    RetrievalPlan,
    RetrievalQuery,
)


@dataclass
class FakeCodeContextProvider:
    responses: dict[str, list[CodeContext]] = field(default_factory=dict)
    failed_queries: set[str] = field(default_factory=set)
    calls: list[tuple[list[str], int]] = field(default_factory=list)

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        self.calls.append((queries, limit))
        query = queries[0]
        if query in self.failed_queries:
            raise RuntimeError("semantic index unavailable")
        return self.responses.get(query, [])


def _query(value: str = "TypeError handle_request") -> RetrievalQuery:
    return RetrievalQuery(
        query=value,
        purpose="Find implementation context",
        priority=60,
        source_hint="source",
    )


def _context(
    *,
    context_id: str = "src/app.py:handle_request",
    snippet: str = "def handle_request():\n    raise TypeError('bad input')",
    relevance_score: float | None = 0.83,
) -> CodeContext:
    return CodeContext(
        context_id=context_id,
        file_path="src/app.py",
        snippet=snippet,
        line_start=10,
        line_end=20,
        function_name="handle_request",
        relevance_score=relevance_score,
        metadata={
            "qualified_symbol": "RequestHandler.handle_request",
            "symbol_type": "method",
            "chunk_number": "2",
            "provider": "fake_semantic_search",
        },
    )


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_converts_code_context_to_candidate() -> None:
    query = _query()
    provider = FakeCodeContextProvider(responses={query.query: [_context()]})

    candidates = await SemanticCodeSearchAdapter(provider).search_semantic_code([query])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_type == RetrievalEvidenceSourceType.CODE_SEMANTIC
    assert candidate.retriever_name == "semantic_code_search"
    assert candidate.file_path == "src/app.py"
    assert candidate.start_line == 10
    assert candidate.end_line == 20
    assert candidate.symbol_name == "RequestHandler.handle_request"
    assert candidate.symbol_type == "method"
    assert candidate.retrieval_query == query.query
    assert candidate.metadata["purpose"] == "Find implementation context"
    assert candidate.metadata["priority"] == 60
    assert candidate.metadata["source_hint"] == "source"
    assert candidate.metadata["original_context_id"] == "src/app.py:handle_request"
    assert candidate.metadata["chunk_number"] == "2"
    assert candidate.metadata["function_name"] == "handle_request"


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_handles_empty_queries() -> None:
    provider = FakeCodeContextProvider()

    candidates = await SemanticCodeSearchAdapter(provider).search_semantic_code([])

    assert candidates == []
    assert provider.calls == []


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_handles_no_results() -> None:
    provider = FakeCodeContextProvider()

    candidates = await SemanticCodeSearchAdapter(provider).search_semantic_code([_query()])

    assert candidates == []


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_handles_multiple_queries() -> None:
    first_query = _query("TypeError")
    second_query = _query("handle_request")
    provider = FakeCodeContextProvider(
        responses={
            first_query.query: [_context()],
            second_query.query: [_context(context_id="src/service.py:run")],
        }
    )

    candidates = await SemanticCodeSearchAdapter(provider).search_semantic_code(
        [first_query, second_query]
    )

    assert [candidate.retrieval_query for candidate in candidates] == [
        "TypeError",
        "handle_request",
    ]
    assert provider.calls == [
        (["TypeError"], 10),
        (["handle_request"], 10),
    ]


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_candidate_id_is_stable() -> None:
    query = _query()
    provider = FakeCodeContextProvider(responses={query.query: [_context()]})
    adapter = SemanticCodeSearchAdapter(provider)

    first_candidates = await adapter.search_semantic_code([query])
    second_candidates = await adapter.search_semantic_code([query])

    assert first_candidates[0].candidate_id == second_candidates[0].candidate_id


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_preserves_semantic_score() -> None:
    query = _query()
    provider = FakeCodeContextProvider(responses={query.query: [_context()]})

    candidates = await SemanticCodeSearchAdapter(provider).search_semantic_code([query])

    assert candidates[0].metadata["semantic_score"] == 0.83


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_skips_blank_content() -> None:
    query = _query()
    blank_context = _context().model_copy(update={"snippet": "   "})
    provider = FakeCodeContextProvider(responses={query.query: [blank_context]})

    candidates = await SemanticCodeSearchAdapter(provider).search_semantic_code([query])

    assert candidates == []


@pytest.mark.asyncio
async def test_semantic_code_search_adapter_continues_after_query_failure() -> None:
    failed_query = _query("first query")
    successful_query = _query("second query")
    provider = FakeCodeContextProvider(
        responses={successful_query.query: [_context()]},
        failed_queries={failed_query.query},
    )

    candidates = await SemanticCodeSearchAdapter(provider).search_semantic_code(
        [failed_query, successful_query]
    )

    assert [candidate.retrieval_query for candidate in candidates] == ["second query"]


@pytest.mark.asyncio
async def test_parallel_context_retriever_accepts_semantic_code_search_adapter() -> None:
    query = _query()
    provider = FakeCodeContextProvider(responses={query.query: [_context()]})
    retriever = ParallelContextRetriever(
        semantic_code_search_provider=SemanticCodeSearchAdapter(provider)
    )

    result = await retriever.retrieve(RetrievalPlan(semantic_queries=[query]))

    assert len(result.candidates) == 1
    assert result.candidates[0].source_type == RetrievalEvidenceSourceType.CODE_SEMANTIC
    assert result.failed_retrievers == []


def test_semantic_code_search_adapter_satisfies_provider_protocol() -> None:
    adapter = SemanticCodeSearchAdapter(FakeCodeContextProvider())

    assert isinstance(adapter, SemanticCodeSearchProvider)
