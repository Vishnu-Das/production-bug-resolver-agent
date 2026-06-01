"""Tests for parallel incident-driven context retrieval."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from bug_resolver.providers.retrieval import (
    CodeGraphExpansionProvider,
    ExactSearchProvider,
    FileContextProvider,
    KnowledgeSearchProvider,
    SemanticCodeSearchProvider,
    StructuralSearchProvider,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    EvidenceCandidate,
    FileContextRequest,
    GraphExpansionRequest,
    RetrievalEvidenceSourceType,
    RetrievalPlan,
    RetrievalQuery,
)


@dataclass
class ConcurrencyProbe:
    """Hold route calls until every expected route has started."""

    expected_calls: int
    started_calls: int = 0
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def wait_for_all_routes(self) -> None:
        self.started_calls += 1
        if self.started_calls == self.expected_calls:
            self.release.set()
        await asyncio.wait_for(self.release.wait(), timeout=0.5)


class AllRoutesProvider:
    def __init__(self, probe: ConcurrencyProbe | None = None) -> None:
        self._probe = probe

    async def read_context(
        self,
        requests: list[FileContextRequest],
    ) -> list[EvidenceCandidate]:
        return await self._candidates("file", RetrievalEvidenceSourceType.FILE_CONTEXT)

    async def search_exact(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        return await self._candidates("exact", RetrievalEvidenceSourceType.CODE_EXACT)

    async def search_structure(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        return await self._candidates(
            "structural",
            RetrievalEvidenceSourceType.CODE_STRUCTURAL,
        )

    async def search_semantic_code(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        return await self._candidates("semantic", RetrievalEvidenceSourceType.CODE_SEMANTIC)

    async def expand_context(
        self,
        requests: list[GraphExpansionRequest],
    ) -> list[EvidenceCandidate]:
        return await self._candidates("graph", RetrievalEvidenceSourceType.CODE_GRAPH)

    async def search_knowledge(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        return await self._candidates("knowledge", RetrievalEvidenceSourceType.KNOWLEDGE_BASE)

    async def _candidates(
        self,
        candidate_id: str,
        source_type: RetrievalEvidenceSourceType,
    ) -> list[EvidenceCandidate]:
        if self._probe is not None:
            await self._probe.wait_for_all_routes()
        return [
            EvidenceCandidate(
                candidate_id=candidate_id,
                source_type=source_type,
                retriever_name=type(self).__name__,
                content=f"{candidate_id} evidence",
            )
        ]


class FailingExactSearchProvider:
    async def search_exact(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        raise RuntimeError("exact index unavailable")


class RecordingSemanticSearchProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def search_semantic_code(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        self.calls += 1
        return []


def _query(value: str) -> RetrievalQuery:
    return RetrievalQuery(query=value, purpose="test retrieval route")


def _full_plan() -> RetrievalPlan:
    return RetrievalPlan(
        file_context_requests=[
            FileContextRequest(file_path="src/app.py", reason="Read incident location")
        ],
        exact_queries=[_query("TypeError")],
        structural_queries=[_query("handle_request")],
        semantic_queries=[_query("Request processing fails")],
        graph_expansion_requests=[
            GraphExpansionRequest(symbol_name="handle_request", reason="Expand incident symbol")
        ],
        kb_queries=[_query("Expected request behavior")],
    )


def test_route_fake_satisfies_retrieval_provider_protocols() -> None:
    provider = AllRoutesProvider()

    assert isinstance(provider, FileContextProvider)
    assert isinstance(provider, ExactSearchProvider)
    assert isinstance(provider, StructuralSearchProvider)
    assert isinstance(provider, SemanticCodeSearchProvider)
    assert isinstance(provider, CodeGraphExpansionProvider)
    assert isinstance(provider, KnowledgeSearchProvider)


@pytest.mark.asyncio
async def test_parallel_context_retriever_runs_available_routes_concurrently(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    probe = ConcurrencyProbe(expected_calls=6)
    provider = AllRoutesProvider(probe)
    retriever = ParallelContextRetriever(
        file_context_provider=provider,
        exact_search_provider=provider,
        structural_search_provider=provider,
        semantic_code_search_provider=provider,
        code_graph_provider=provider,
        knowledge_search_provider=provider,
    )

    result = await asyncio.wait_for(retriever.retrieve(_full_plan()), timeout=1.0)

    assert probe.started_calls == 6
    assert [candidate.candidate_id for candidate in result.candidates] == [
        "file",
        "exact",
        "structural",
        "semantic",
        "graph",
        "knowledge",
    ]
    assert result.failed_retrievers == []
    assert result.failures == []
    assert result.warnings == []
    assert "parallel context retrieval started routes=6" in caplog.text
    assert "parallel retrieval route finished route=exact_search" in caplog.text
    assert "parallel context retrieval finished routes=6 candidates=6 failures=0" in caplog.text


@pytest.mark.asyncio
async def test_parallel_context_retriever_preserves_successes_when_provider_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    successful_provider = AllRoutesProvider()
    retriever = ParallelContextRetriever(
        exact_search_provider=FailingExactSearchProvider(),
        semantic_code_search_provider=successful_provider,
    )
    plan = RetrievalPlan(
        exact_queries=[_query("TypeError")],
        semantic_queries=[_query("Request processing fails")],
    )

    result = await retriever.retrieve(plan)

    assert [candidate.candidate_id for candidate in result.candidates] == ["semantic"]
    assert result.failed_retrievers == ["exact_search"]
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.route == "exact_search"
    assert failure.provider_name == "FailingExactSearchProvider"
    assert failure.error_type == "RuntimeError"
    assert failure.message == "exact index unavailable"
    assert result.warnings == [
        "exact_search retrieval failed in FailingExactSearchProvider: "
        "RuntimeError: exact index unavailable"
    ]
    assert "exact index unavailable" in caplog.text


@pytest.mark.asyncio
async def test_parallel_context_retriever_skips_route_without_planned_requests() -> None:
    provider = RecordingSemanticSearchProvider()
    retriever = ParallelContextRetriever(semantic_code_search_provider=provider)

    result = await retriever.retrieve(RetrievalPlan())

    assert provider.calls == 0
    assert result.candidates == []
    assert result.failed_retrievers == []
    assert result.failures == []
    assert result.warnings == []


@pytest.mark.asyncio
async def test_parallel_context_retriever_handles_no_configured_providers() -> None:
    result = await ParallelContextRetriever().retrieve(_full_plan())

    assert result.candidates == []
    assert result.failed_retrievers == []
    assert result.failures == []
    assert result.warnings == []
