from __future__ import annotations

import pytest

from bug_resolver.agents import EvidenceEvaluatorAgent
from bug_resolver.schemas import (
    EvidenceItem,
    EvidenceSourceType,
    Incident,
    WorkflowState,
)


def make_state(**overrides: object) -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Summary route fails",
            description="Users get 500 errors when asking summary questions.",
            affected_service="conversational_rag",
        ),
        **overrides,
    )


def log_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev-log-1",
        source_type=EvidenceSourceType.LOG,
        source_name="app.log",
        content="TypeError in route_query",
        confidence=1.0,
    )


def code_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev-code-1",
        source_type=EvidenceSourceType.CODE,
        source_name="src/rag/router.py",
        file_path="src/rag/router.py",
        line_start=40,
        line_end=45,
        content="def route_query(...): return response['output']",
        relevance_score=0.9,
    )


def knowledge_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev-kb-1",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="README.md",
        content="The router should return a structured response.",
        relevance_score=0.8,
    )


@pytest.mark.asyncio
async def test_evidence_evaluator_requires_retry_when_no_evidence_exists() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state()

    result = await agent.run(state)

    assert result.evaluation_id.startswith("EVAL-")
    assert result.incident_id == "INC-001"
    assert result.confidence_score == 0.0
    assert result.can_write_rca is False
    assert result.retry_required is True
    assert "No evidence has been collected yet." in result.missing_evidence
    assert "Runtime log evidence is missing." in result.missing_evidence
    assert "Implementation code evidence is missing." in result.missing_evidence
    assert result.improved_code_queries != []
    assert result.improved_knowledge_queries != []
    assert result.reason == (
        "Evidence is incomplete; supervisor should replan for more evidence."
    )


@pytest.mark.asyncio
async def test_evidence_evaluator_requires_more_evidence_for_log_only_state() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state()
    state.add_evidence(log_evidence())

    result = await agent.run(state)

    assert result.confidence_score == 0.5
    assert result.can_write_rca is False
    assert result.retry_required is True
    assert "Implementation code evidence is missing." in result.missing_evidence
    assert "Minimum evidence count has not been met before RCA writing." in (
        result.missing_evidence
    )
    assert "TypeError in route_query" in result.improved_code_queries


@pytest.mark.asyncio
async def test_evidence_evaluator_allows_rca_when_evidence_is_sufficient() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(confidence_threshold=0.75)
    state.add_evidence(log_evidence())
    state.add_evidence(code_evidence())
    state.add_evidence(knowledge_evidence())

    result = await agent.run(state)

    assert result.confidence_score == 0.97
    assert result.can_write_rca is True
    assert result.retry_required is False
    assert result.missing_evidence == []
    assert result.improved_code_queries == []
    assert result.improved_knowledge_queries == []
    assert result.reason == "Evidence is sufficient to proceed to RCA writing."


@pytest.mark.asyncio
async def test_evidence_evaluator_stops_retry_when_replans_are_exhausted() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(max_replans=0)
    state.add_evidence(log_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is False
    assert result.retry_required is False
    assert "Maximum replans have been reached." in result.missing_evidence
    assert result.improved_code_queries == []
    assert result.improved_knowledge_queries == []
    assert result.reason == (
        "Evidence is incomplete, but replanning is no longer available under "
        "the configured limits."
    )
