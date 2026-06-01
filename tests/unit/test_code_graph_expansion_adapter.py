"""Tests for adapting AST code graph search into retrieval candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bug_resolver.providers.retrieval import (
    CodeGraphExpansionAdapter,
    CodeGraphExpansionProvider,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    CodeGraphContext,
    GraphExpansionRequest,
    RetrievalEvidenceSourceType,
    RetrievalPlan,
)


@dataclass
class FakeCodeGraphProvider:
    responses: dict[str, list[CodeGraphContext]] = field(default_factory=dict)
    failed_queries: set[str] = field(default_factory=set)
    calls: list[tuple[list[str], int]] = field(default_factory=list)

    async def search_graph(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeGraphContext]:
        self.calls.append((queries, limit))
        query = queries[0]
        if query in self.failed_queries:
            raise RuntimeError("graph index unavailable")
        return self.responses.get(query, [])


def _request(
    *,
    file_path: str | None = "src/app.py",
    symbol_name: str | None = "handle_request",
    line_number: int | None = 12,
) -> GraphExpansionRequest:
    return GraphExpansionRequest(
        file_path=file_path,
        symbol_name=symbol_name,
        line_number=line_number,
        max_depth=1,
        reason="Expand around stack trace function",
    )


def _context(
    *,
    context_id: str = "src/app.py:handle_request",
    relative_path: str = "src/app.py",
    symbol_name: str = "handle_request",
    qualified_symbol: str = "handle_request",
    content: str = "handle_request calls validate_input",
    metadata: dict[str, str] | None = None,
) -> CodeGraphContext:
    return CodeGraphContext(
        context_id=context_id,
        file_path=relative_path,
        relative_path=relative_path,
        symbol_name=symbol_name,
        symbol_type="function",
        qualified_symbol=qualified_symbol,
        line_start=10,
        line_end=20,
        calls=["validate_input"],
        content=content,
        relevance_score=0.8,
        metadata=metadata or {
            "relationship_type": "caller",
            "graph_distance": "1",
            "source_symbol": "handle_request",
            "target_symbol": "validate_input",
        },
    )


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_converts_graph_context_to_candidate() -> None:
    request = _request()
    provider = FakeCodeGraphProvider(responses={"src/app.py handle_request": [_context()]})

    candidates = await CodeGraphExpansionAdapter(provider).expand_context([request])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_type == RetrievalEvidenceSourceType.CODE_GRAPH
    assert candidate.retriever_name == "code_graph_expansion"
    assert candidate.file_path == "src/app.py"
    assert candidate.start_line == 10
    assert candidate.end_line == 20
    assert candidate.symbol_name == "handle_request"
    assert candidate.symbol_type == "function"
    assert candidate.retrieval_query == "src/app.py handle_request"
    assert candidate.metadata["reason"] == "Expand around stack trace function"
    assert candidate.metadata["graph_distance"] == 1
    assert candidate.metadata["relationship_type"] == "caller"
    assert candidate.metadata["request_file_path"] == "src/app.py"
    assert candidate.metadata["request_symbol_name"] == "handle_request"
    assert candidate.metadata["request_line_number"] == 12
    assert candidate.metadata["calls"] == ["validate_input"]


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_handles_empty_requests() -> None:
    provider = FakeCodeGraphProvider()

    candidates = await CodeGraphExpansionAdapter(provider).expand_context([])

    assert candidates == []
    assert provider.calls == []


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_handles_no_results() -> None:
    provider = FakeCodeGraphProvider()

    candidates = await CodeGraphExpansionAdapter(provider).expand_context([_request()])

    assert candidates == []


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_handles_multiple_requests() -> None:
    file_request = _request(symbol_name=None, line_number=4)
    symbol_request = _request(file_path=None, symbol_name="validate_input", line_number=None)
    provider = FakeCodeGraphProvider(
        responses={
            "src/app.py": [_context()],
            "validate_input": [
                _context(
                    context_id="src/validation.py:validate_input",
                    relative_path="src/validation.py",
                    symbol_name="validate_input",
                    qualified_symbol="validate_input",
                )
            ],
        }
    )

    candidates = await CodeGraphExpansionAdapter(provider).expand_context(
        [file_request, symbol_request]
    )

    assert len(candidates) == 2
    assert candidates[0].metadata["request_file_path"] == "src/app.py"
    assert candidates[0].metadata["request_line_number"] == 4
    assert candidates[1].metadata["request_symbol_name"] == "validate_input"
    assert provider.calls == [
        (["src/app.py"], 10),
        (["validate_input"], 10),
    ]


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_candidate_id_is_stable() -> None:
    request = _request()
    provider = FakeCodeGraphProvider(responses={"src/app.py handle_request": [_context()]})
    adapter = CodeGraphExpansionAdapter(provider)

    first_candidates = await adapter.expand_context([request])
    second_candidates = await adapter.expand_context([request])

    assert first_candidates[0].candidate_id == second_candidates[0].candidate_id


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_preserves_graph_distance() -> None:
    request = _request()
    provider = FakeCodeGraphProvider(responses={"src/app.py handle_request": [_context()]})

    candidates = await CodeGraphExpansionAdapter(provider).expand_context([request])

    assert candidates[0].metadata["graph_distance"] == 1


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_creates_meaningful_content_when_blank() -> None:
    request = _request()
    blank_context = _context().model_copy(update={"content": "   "})
    provider = FakeCodeGraphProvider(responses={"src/app.py handle_request": [blank_context]})

    candidates = await CodeGraphExpansionAdapter(provider).expand_context([request])

    assert candidates[0].content == (
        "Graph context: handle_request in src/app.py has calls relationships."
    )


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_skips_unsearchable_line_only_request() -> None:
    provider = FakeCodeGraphProvider()
    request = GraphExpansionRequest(line_number=12, reason="Expand incident line")

    candidates = await CodeGraphExpansionAdapter(provider).expand_context([request])

    assert candidates == []
    assert provider.calls == []


@pytest.mark.asyncio
async def test_code_graph_expansion_adapter_continues_after_request_failure() -> None:
    failed_request = _request(file_path=None, symbol_name="first_symbol", line_number=None)
    successful_request = _request(file_path=None, symbol_name="second_symbol", line_number=None)
    provider = FakeCodeGraphProvider(
        responses={"second_symbol": [_context()]},
        failed_queries={"first_symbol"},
    )

    candidates = await CodeGraphExpansionAdapter(provider).expand_context(
        [failed_request, successful_request]
    )

    assert [candidate.retrieval_query for candidate in candidates] == ["second_symbol"]


@pytest.mark.asyncio
async def test_parallel_context_retriever_accepts_code_graph_expansion_adapter() -> None:
    request = _request()
    provider = FakeCodeGraphProvider(responses={"src/app.py handle_request": [_context()]})
    retriever = ParallelContextRetriever(
        code_graph_provider=CodeGraphExpansionAdapter(provider)
    )

    result = await retriever.retrieve(RetrievalPlan(graph_expansion_requests=[request]))

    assert len(result.candidates) == 1
    assert result.candidates[0].source_type == RetrievalEvidenceSourceType.CODE_GRAPH
    assert result.failed_retrievers == []


def test_code_graph_expansion_adapter_satisfies_provider_protocol() -> None:
    adapter = CodeGraphExpansionAdapter(FakeCodeGraphProvider())

    assert isinstance(adapter, CodeGraphExpansionProvider)
