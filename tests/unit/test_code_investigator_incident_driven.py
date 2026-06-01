"""Tests for the optional incident-driven code investigation path."""

from __future__ import annotations

from typing import Any

import pytest

from bug_resolver.agents import CodeInvestigatorAgent, CodeInvestigatorInput
from bug_resolver.rules import RankedEvidenceConversionRules
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    CodeContext,
    EvidenceCandidate,
    EvidenceItem,
    EvidenceScoreBreakdown,
    EvidenceSourceType,
    Incident,
    IncidentDrivenContextResult,
    IncidentFacts,
    RankedEvidence,
    RetrievalEvidenceEvaluationResult,
    RetrievalEvidenceSourceType,
    RetrievalPlan,
)


def make_decision() -> AgentDecision:
    return AgentDecision(
        decision_id="decision-1",
        next_agent=AgentName.CODE_INVESTIGATOR,
        reason="Need implementation context.",
        queries=["handle_request TypeError"],
        expected_evidence=["source context"],
    )


def make_ranked_evidence(
    *,
    candidate_id: str = "selected-code",
    content: str = "42: def handle_request():\n43:     raise TypeError('bad input')",
    score: float = 0.91,
) -> RankedEvidence:
    return RankedEvidence(
        candidate=EvidenceCandidate(
            candidate_id=candidate_id,
            source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
            retriever_name="file_context",
            content=content,
            file_path="src/app.py",
            start_line=42,
            end_line=43,
            symbol_name="handle_request",
            symbol_type="function",
            retrieval_query="TypeError handle_request",
            metadata={"retrieved_by": ["file_context", "exact_search"]},
        ),
        score=EvidenceScoreBreakdown(
            final_score=score,
            reasons=["Candidate file matches stack trace file src/app.py"],
        ),
        rank=1,
        supporting_candidate_ids=["exact-code"],
    )


def make_context_result(
    *,
    ranked_evidence: list[RankedEvidence] | None = None,
    raw_candidates: list[EvidenceCandidate] | None = None,
    failed_retrievers: list[str] | None = None,
    retrieval_warnings: list[str] | None = None,
) -> IncidentDrivenContextResult:
    selected = ranked_evidence or [make_ranked_evidence()]
    return IncidentDrivenContextResult(
        facts=IncidentFacts(
            incident_id="INC-001",
            summary="Request fails with TypeError",
        ),
        retrieval_plan=RetrievalPlan(),
        raw_candidates=raw_candidates or [evidence.candidate for evidence in selected],
        normalized_candidates=[],
        deduplicated_candidates=[],
        evaluation=RetrievalEvidenceEvaluationResult(
            ranked_evidence=selected,
            selected_evidence=selected,
            has_direct_code_evidence=True,
            sufficient_for_rca=True,
            confidence=0.91,
        ),
        failed_retrievers=failed_retrievers or [],
        retrieval_warnings=retrieval_warnings or [],
    )


class RecordingContextService:
    def __init__(self, result: IncidentDrivenContextResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def build_context(self, **kwargs: Any) -> IncidentDrivenContextResult:
        self.calls.append(kwargs)
        return self.result


class FailIfCalledCodeProvider:
    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        raise AssertionError("legacy provider should not be called")


class RecordingCodeProvider:
    def __init__(self) -> None:
        self.queries: list[str] | None = None

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        self.queries = queries
        return [
            CodeContext(
                context_id="legacy-code",
                file_path="src/app.py",
                snippet="def handle_request(): ...",
            )
        ]


def make_incident() -> Incident:
    return Incident(
        incident_id="INC-001",
        title="Request fails with TypeError",
        description="Inspect the failing request path.",
        raw_input="reported_from=api",
    )


@pytest.mark.asyncio
async def test_code_investigator_uses_injected_incident_driven_context_service() -> None:
    service = RecordingContextService(make_context_result())
    agent = CodeInvestigatorAgent(
        FailIfCalledCodeProvider(),
        incident_driven_context_service=service,
    )

    evidence = await agent.run(
        CodeInvestigatorInput(
            decision=make_decision(),
            incident=make_incident(),
        )
    )

    assert len(service.calls) == 1
    assert [item.evidence_id for item in evidence] == ["selected-code"]
    assert evidence[0].source_type == EvidenceSourceType.CODE


@pytest.mark.asyncio
async def test_code_investigator_preserves_legacy_route_without_context_service() -> None:
    provider = RecordingCodeProvider()
    agent = CodeInvestigatorAgent(provider)

    evidence = await agent.run(CodeInvestigatorInput(decision=make_decision()))

    assert provider.queries
    assert [item.evidence_id for item in evidence] == ["evidence-legacy-code"]


def test_ranked_evidence_conversion_preserves_code_metadata() -> None:
    evidence = RankedEvidenceConversionRules().convert_selected(
        make_context_result(),
        agent_name="code_investigator_agent",
        decision_id="decision-1",
    )

    assert len(evidence) == 1
    assert evidence[0].file_path == "src/app.py"
    assert evidence[0].line_start == 42
    assert evidence[0].line_end == 43
    assert evidence[0].relevance_score == 0.91
    assert evidence[0].metadata["symbol_name"] == "handle_request"
    assert evidence[0].metadata["retrieval_query"] == "TypeError handle_request"
    assert evidence[0].metadata["retriever_name"] == "file_context"
    assert "Candidate file matches stack trace file" in evidence[0].metadata[
        "score_reasons"
    ]


@pytest.mark.asyncio
async def test_code_investigator_forwards_prior_raw_log_evidence_to_service() -> None:
    service = RecordingContextService(make_context_result())
    agent = CodeInvestigatorAgent(
        FailIfCalledCodeProvider(),
        incident_driven_context_service=service,
    )
    raw_log = 'File "src/app.py", line 42, in handle_request\nTypeError: bad input'

    await agent.run(
        CodeInvestigatorInput(
            decision=make_decision(),
            incident=make_incident(),
            evidence_items=[
                EvidenceItem(
                    evidence_id="log-1",
                    source_type=EvidenceSourceType.LOG,
                    source_name="runtime.log",
                    content=raw_log,
                )
            ],
        )
    )

    assert service.calls[0]["log_texts"] == [raw_log]
    assert service.calls[0]["metadata"]["raw_input"] == "reported_from=api"


@pytest.mark.asyncio
async def test_code_investigator_preserves_retrieval_failure_warnings() -> None:
    service = RecordingContextService(
        make_context_result(
            failed_retrievers=["exact_search"],
            retrieval_warnings=["exact_search retrieval failed"],
        )
    )
    agent = CodeInvestigatorAgent(
        FailIfCalledCodeProvider(),
        incident_driven_context_service=service,
    )

    evidence = await agent.run(
        CodeInvestigatorInput(
            decision=make_decision(),
            incident=make_incident(),
        )
    )

    assert evidence[0].metadata["failed_retrievers"] == '["exact_search"]'
    assert evidence[0].metadata["retrieval_warnings"] == (
        '["exact_search retrieval failed"]'
    )


@pytest.mark.asyncio
async def test_code_investigator_forwards_only_selected_ranked_evidence() -> None:
    unselected = EvidenceCandidate(
        candidate_id="raw-unselected",
        source_type=RetrievalEvidenceSourceType.CODE_SEMANTIC,
        retriever_name="semantic_code_search",
        content="Unrelated semantic context",
    )
    selected = make_ranked_evidence()
    service = RecordingContextService(
        make_context_result(
            ranked_evidence=[selected],
            raw_candidates=[selected.candidate, unselected],
        )
    )
    agent = CodeInvestigatorAgent(
        FailIfCalledCodeProvider(),
        incident_driven_context_service=service,
    )

    evidence = await agent.run(
        CodeInvestigatorInput(
            decision=make_decision(),
            incident=make_incident(),
        )
    )

    assert [item.evidence_id for item in evidence] == ["selected-code"]
