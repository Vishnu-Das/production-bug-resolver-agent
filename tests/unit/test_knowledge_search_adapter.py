"""Tests for adapting knowledge-base search into retrieval candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bug_resolver.providers.retrieval import (
    KnowledgeSearchAdapter,
    KnowledgeSearchProvider,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    KnowledgeContext,
    RetrievalEvidenceSourceType,
    RetrievalPlan,
    RetrievalQuery,
)


@dataclass
class FakeKnowledgeBaseProvider:
    responses: dict[str, list[KnowledgeContext]] = field(default_factory=dict)
    failed_queries: set[str] = field(default_factory=set)
    calls: list[tuple[list[str], int]] = field(default_factory=list)

    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        self.calls.append((queries, limit))
        query = queries[0]
        if query in self.failed_queries:
            raise RuntimeError("documentation index unavailable")
        return self.responses.get(query, [])


def _query(value: str = "results are empty") -> RetrievalQuery:
    return RetrievalQuery(
        query=value,
        purpose="Find documentation for expected behavior",
        priority=50,
        source_hint="documentation",
    )


def _context(
    *,
    context_id: str = "docs/behavior.md:expected",
    content: str = "The endpoint should return ranked results.",
    relevance_score: float | None = 0.82,
) -> KnowledgeContext:
    return KnowledgeContext(
        context_id=context_id,
        document_name="Behavior guide",
        content=content,
        section_title="Expected behavior",
        file_path="docs/behavior.md",
        relevance_score=relevance_score,
        metadata={
            "chunk_id": "expected",
            "line_start": "10",
            "line_end": "14",
            "provider": "fake_knowledge_search",
        },
    )


@pytest.mark.asyncio
async def test_knowledge_search_adapter_converts_context_to_candidate() -> None:
    query = _query()
    provider = FakeKnowledgeBaseProvider(responses={query.query: [_context()]})

    candidates = await KnowledgeSearchAdapter(provider).search_knowledge([query])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_type == RetrievalEvidenceSourceType.KNOWLEDGE_BASE
    assert candidate.retriever_name == "knowledge_search"
    assert candidate.file_path == "docs/behavior.md"
    assert candidate.start_line == 10
    assert candidate.end_line == 14
    assert "ranked results" in candidate.content
    assert candidate.retrieval_query == query.query
    assert candidate.metadata["purpose"] == "Find documentation for expected behavior"
    assert candidate.metadata["priority"] == 50
    assert candidate.metadata["source_hint"] == "documentation"
    assert candidate.metadata["document_title"] == "Behavior guide"
    assert candidate.metadata["section"] == "Expected behavior"
    assert candidate.metadata["score"] == 0.82
    assert candidate.metadata["original_context_id"] == "docs/behavior.md:expected"
    assert candidate.metadata["chunk_id"] == "expected"


@pytest.mark.asyncio
async def test_knowledge_search_adapter_handles_empty_queries() -> None:
    provider = FakeKnowledgeBaseProvider()

    candidates = await KnowledgeSearchAdapter(provider).search_knowledge([])

    assert candidates == []
    assert provider.calls == []


@pytest.mark.asyncio
async def test_knowledge_search_adapter_handles_no_results() -> None:
    provider = FakeKnowledgeBaseProvider()

    candidates = await KnowledgeSearchAdapter(provider).search_knowledge([_query()])

    assert candidates == []


@pytest.mark.asyncio
async def test_knowledge_search_adapter_handles_multiple_queries() -> None:
    first_query = _query("expected behavior")
    second_query = _query("troubleshooting notes")
    provider = FakeKnowledgeBaseProvider(
        responses={
            first_query.query: [_context()],
            second_query.query: [_context(context_id="docs/notes.md:troubleshooting")],
        }
    )

    candidates = await KnowledgeSearchAdapter(provider).search_knowledge(
        [first_query, second_query]
    )

    assert [candidate.retrieval_query for candidate in candidates] == [
        "expected behavior",
        "troubleshooting notes",
    ]
    assert provider.calls == [
        (["expected behavior"], 5),
        (["troubleshooting notes"], 5),
    ]


@pytest.mark.asyncio
async def test_knowledge_search_adapter_candidate_id_is_stable() -> None:
    query = _query()
    provider = FakeKnowledgeBaseProvider(responses={query.query: [_context()]})
    adapter = KnowledgeSearchAdapter(provider)

    first_candidates = await adapter.search_knowledge([query])
    second_candidates = await adapter.search_knowledge([query])

    assert first_candidates[0].candidate_id == second_candidates[0].candidate_id


@pytest.mark.asyncio
async def test_knowledge_search_adapter_preserves_score() -> None:
    query = _query()
    provider = FakeKnowledgeBaseProvider(responses={query.query: [_context()]})

    candidates = await KnowledgeSearchAdapter(provider).search_knowledge([query])

    assert candidates[0].metadata["score"] == 0.82


@pytest.mark.asyncio
async def test_knowledge_search_adapter_skips_blank_content() -> None:
    query = _query()
    blank_context = _context().model_copy(update={"content": "   "})
    provider = FakeKnowledgeBaseProvider(responses={query.query: [blank_context]})

    candidates = await KnowledgeSearchAdapter(provider).search_knowledge([query])

    assert candidates == []


@pytest.mark.asyncio
async def test_knowledge_search_adapter_continues_after_query_failure() -> None:
    failed_query = _query("first query")
    successful_query = _query("second query")
    provider = FakeKnowledgeBaseProvider(
        responses={successful_query.query: [_context()]},
        failed_queries={failed_query.query},
    )

    candidates = await KnowledgeSearchAdapter(provider).search_knowledge(
        [failed_query, successful_query]
    )

    assert [candidate.retrieval_query for candidate in candidates] == ["second query"]


@pytest.mark.asyncio
async def test_parallel_context_retriever_accepts_knowledge_search_adapter() -> None:
    query = _query()
    provider = FakeKnowledgeBaseProvider(responses={query.query: [_context()]})
    retriever = ParallelContextRetriever(
        knowledge_search_provider=KnowledgeSearchAdapter(provider)
    )

    result = await retriever.retrieve(RetrievalPlan(kb_queries=[query]))

    assert len(result.candidates) == 1
    assert result.candidates[0].source_type == RetrievalEvidenceSourceType.KNOWLEDGE_BASE
    assert result.failed_retrievers == []


def test_knowledge_search_adapter_satisfies_provider_protocol() -> None:
    adapter = KnowledgeSearchAdapter(FakeKnowledgeBaseProvider())

    assert isinstance(adapter, KnowledgeSearchProvider)
