"""Tests for incident-driven retrieval service orchestration."""

from __future__ import annotations

from datetime import datetime

import pytest

from bug_resolver.retrieval.incident_driven_context_service import (
    IncidentDrivenContextService,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    EvidenceCandidate,
    FileContextRequest,
    GraphExpansionRequest,
    Incident,
    IncidentFacts,
    LogEntry,
    LogLevel,
    RetrievalEvidenceSourceType,
    RetrievalQuery,
)


class OverlappingFileContextProvider:
    async def read_context(
        self,
        requests: list[FileContextRequest],
    ) -> list[EvidenceCandidate]:
        assert requests[0].file_path == "src/app.py"
        return [
            EvidenceCandidate(
                candidate_id="file-context",
                source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
                retriever_name="file_context",
                content="\n42: def handle_request():\n43:     raise TypeError('bad input')\n",
                file_path="./src\\app.py",
                start_line=40,
                end_line=50,
                matched_terms=[" TypeError ", "TypeError"],
            )
        ]


class OverlappingExactSearchProvider:
    async def search_exact(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        assert queries
        return [
            EvidenceCandidate(
                candidate_id="exact-context",
                source_type=RetrievalEvidenceSourceType.CODE_EXACT,
                retriever_name="exact_search",
                content="42: def handle_request():\n43:     raise TypeError('bad input')",
                file_path="src/app.py",
                start_line=42,
                end_line=43,
                matched_terms=["TypeError"],
            )
        ]


class FailingExactSearchProvider:
    async def search_exact(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        raise RuntimeError("exact search unavailable")


class RankedOwnerExactSearchProvider:
    async def search_exact(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        assert any(query.query == "record_fingerprint" for query in queries)
        return [
            EvidenceCandidate(
                candidate_id="owner-exact",
                source_type=RetrievalEvidenceSourceType.CODE_EXACT,
                retriever_name="exact_search",
                content="12: record_fingerprint = build_fingerprint(record)",
                file_path="src/worker.py",
                start_line=12,
                end_line=12,
                matched_terms=["record_fingerprint"],
            )
        ]


class RecordingOwnerGraphProvider:
    def __init__(self) -> None:
        self.requests: list[GraphExpansionRequest] = []

    async def expand_context(
        self,
        requests: list[GraphExpansionRequest],
    ) -> list[EvidenceCandidate]:
        self.requests.extend(requests)
        return [
            EvidenceCandidate(
                candidate_id="owner-graph",
                source_type=RetrievalEvidenceSourceType.CODE_GRAPH,
                retriever_name="code_graph_expansion",
                content="Graph context: process_record calls build_fingerprint",
                file_path="src/worker.py",
                symbol_name="process_record",
                metadata={"graph_distance": 1},
            )
        ]


@pytest.mark.asyncio
async def test_incident_driven_context_service_runs_full_pipeline(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    service = IncidentDrivenContextService(
        ParallelContextRetriever(
            file_context_provider=OverlappingFileContextProvider(),
            exact_search_provider=OverlappingExactSearchProvider(),
        )
    )

    result = await service.build_context(
        incident_id="INC-001",
        summary='Request fails with TypeError and "bad input"',
        log_texts=[
            'Traceback (most recent call last):\n'
            '  File "src/app.py", line 42, in handle_request\n'
            "TypeError: bad input"
        ],
    )

    assert result.facts.exception_types == ["TypeError"]
    assert "bad input" in result.facts.quoted_terms
    assert result.retrieval_plan.file_context_requests[0].file_path == "src/app.py"
    assert len(result.raw_candidates) == 2
    assert result.normalized_candidates[0].file_path == "src/app.py"
    assert result.normalized_candidates[0].matched_terms == ["TypeError"]
    assert len(result.deduplicated_candidates) == 1
    assert result.deduplicated_candidates[0].metadata["retrieved_by"] == [
        "file_context",
        "exact_search",
    ]
    assert result.evaluation.has_direct_code_evidence is True
    assert result.evaluation.sufficient_for_rca is True
    assert result.evaluation.selected_evidence
    assert "incident facts parsed incident_id=INC-001" in caplog.text
    assert "retrieval plan built incident_id=INC-001" in caplog.text
    assert "incident-driven context build started incident_id=INC-001" in caplog.text
    assert "raw=2 normalized=2 deduplicated=1 ranked=1 selected=1" in caplog.text
    assert "direct_code=True sufficient_for_rca=True" in caplog.text


@pytest.mark.asyncio
async def test_incident_driven_context_service_preserves_retrieval_warnings() -> None:
    service = IncidentDrivenContextService(
        ParallelContextRetriever(
            file_context_provider=OverlappingFileContextProvider(),
            exact_search_provider=FailingExactSearchProvider(),
        )
    )

    result = await service.build_context(
        incident_id="INC-002",
        summary="Request fails with TypeError",
        log_texts=['File "src/app.py", line 42, in handle_request\nTypeError: bad input'],
    )

    assert len(result.deduplicated_candidates) == 1
    assert result.failed_retrievers == ["exact_search"]
    assert any("exact search unavailable" in warning for warning in result.retrieval_warnings)


@pytest.mark.asyncio
async def test_service_accepts_existing_incident_and_log_schemas() -> None:
    incident = Incident(
        incident_id="INC-003",
        title="Request failed",
        description="Inspect runtime context",
    )
    logs = [
        LogEntry(
            log_id="log-1",
            message="trace_id=trace-123 request_id=req-456",
            level=LogLevel.ERROR,
            timestamp=datetime(2026, 5, 30),
        )
    ]

    result = await IncidentDrivenContextService(
        ParallelContextRetriever()
    ).build_context_for_incident(incident, logs)

    assert result.facts.trace_ids == ["trace-123"]
    assert result.facts.request_ids == ["req-456"]
    assert result.raw_candidates == []
    assert result.evaluation.sufficient_for_rca is False


@pytest.mark.asyncio
async def test_incident_driven_context_service_handles_no_candidates() -> None:
    facts = IncidentFacts(
        incident_id="INC-004",
        summary="Minimal incident context",
    )

    result = await IncidentDrivenContextService(
        ParallelContextRetriever()
    ).build_context_from_facts(facts)

    assert result.facts == facts
    assert result.retrieval_plan.semantic_queries
    assert result.retrieval_plan.kb_queries
    assert result.raw_candidates == []
    assert result.normalized_candidates == []
    assert result.deduplicated_candidates == []
    assert result.evaluation.sufficient_for_rca is False
    assert "No evidence met the minimum selection score" in result.evaluation.warnings


@pytest.mark.asyncio
async def test_incident_driven_context_service_deduplicates_before_ranking() -> None:
    service = IncidentDrivenContextService(
        ParallelContextRetriever(
            file_context_provider=OverlappingFileContextProvider(),
            exact_search_provider=OverlappingExactSearchProvider(),
        )
    )

    result = await service.build_context(
        incident_id="INC-005",
        summary="Request fails with TypeError",
        log_texts=['File "src/app.py", line 42, in handle_request\nTypeError: bad input'],
    )

    assert len(result.raw_candidates) == 2
    assert len(result.deduplicated_candidates) == 1
    assert len(result.evaluation.ranked_evidence) == 1


@pytest.mark.asyncio
async def test_incident_driven_context_service_expands_graph_from_ranked_owner() -> None:
    graph_provider = RecordingOwnerGraphProvider()
    service = IncidentDrivenContextService(
        ParallelContextRetriever(
            exact_search_provider=RankedOwnerExactSearchProvider(),
            code_graph_provider=graph_provider,
        )
    )

    result = await service.build_context(
        incident_id="INC-006",
        summary="Duplicate record was accepted",
        log_texts=[
            "record_fingerprint=abc event=duplicate_record_detected "
            "action=processing_started"
        ],
    )

    assert graph_provider.requests == [
        GraphExpansionRequest(
            file_path="src/worker.py",
            line_number=12,
            max_depth=1,
            reason="Expand graph context from ranked implementation owner src/worker.py",
        )
    ]
    assert result.retrieval_plan.graph_expansion_requests == graph_provider.requests
    assert {candidate.candidate_id for candidate in result.raw_candidates} == {
        "owner-exact",
        "owner-graph",
    }
    assert {candidate.candidate_id for candidate in result.deduplicated_candidates} == {
        "owner-exact",
        "owner-graph",
    }
    candidates_by_id = {
        candidate.candidate_id: candidate
        for candidate in result.deduplicated_candidates
    }
    assert candidates_by_id["owner-exact"].content == (
        "12: record_fingerprint = build_fingerprint(record)"
    )
    assert candidates_by_id["owner-graph"].content == (
        "Graph context: process_record calls build_fingerprint"
    )
    assert any(
        evidence.candidate.source_type == RetrievalEvidenceSourceType.CODE_GRAPH
        for evidence in result.evaluation.ranked_evidence
    )
