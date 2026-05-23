"""Tests for evidence sufficiency decisions made by the evaluator agent."""

from __future__ import annotations

import pytest

from bug_resolver.agents import EvidenceEvaluatorAgent
from bug_resolver.schemas import (
    AgentName,
    EvidenceItem,
    EvidenceSourceType,
    Incident,
    WorkflowState,
)


def make_state(**overrides: object) -> WorkflowState:
    incident = overrides.pop(
        "incident",
        Incident(
            incident_id="INC-001",
            title="Summary route fails",
            description="Users get 500 errors when asking summary questions.",
            affected_service="conversational_rag",
        ),
    )
    return WorkflowState(
        incident=incident,
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


def generic_implementation_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev-code-generic",
        source_type=EvidenceSourceType.CODE,
        source_name="src/service.py",
        file_path="src/service.py",
        line_start=10,
        line_end=20,
        content="def choose_strategy(query): return selected_strategy",
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


def graph_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev-graph-1",
        source_type=EvidenceSourceType.GRAPH,
        source_name="src/reranker.py",
        file_path="src/reranker.py",
        line_start=10,
        line_end=20,
        content=(
            "src/reranker.py:rerank_documents_with_scores calls load_reranker "
            "and reads RERANKING_MODEL_NAME."
        ),
        relevance_score=0.9,
        metadata={"qualified_symbol": "rerank_documents_with_scores"},
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
    assert result.reason == ("Evidence is incomplete; supervisor should replan for more evidence.")


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
async def test_evidence_evaluator_requests_kb_for_expected_behavior_mismatch() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(
        confidence_threshold=0.75,
        incident=Incident(
            incident_id="INC-BEHAVIOR",
            title="Successful responses contain wrong results",
            description=(
                "Users report that the service still returns a successful response, "
                "but the result is incorrect and expected behavior is unclear after deployment."
            ),
            affected_service="generic_service",
        ),
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-behavior",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="request completed status=200 selected_strategy=fast_path",
        )
    )
    state.add_evidence(generic_implementation_evidence())

    result = await agent.run(state)

    assert result.confidence_score == 0.8
    assert result.can_write_rca is False
    assert result.retry_required is True
    assert (
        "Knowledge-base evidence is missing for expected behavior, policy, "
        "configuration, deployment, or quality expectations."
        in result.missing_evidence
    )
    assert result.improved_knowledge_queries != []
    assert result.reason == (
        "Knowledge-base evidence is needed before RCA because the incident "
        "context indicates a behavior, policy, configuration, deployment, "
        "or quality expectation mismatch."
    )


@pytest.mark.asyncio
async def test_evidence_evaluator_does_not_require_kb_for_clear_exception() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(
        confidence_threshold=0.75,
        incident=Incident(
            incident_id="INC-EXCEPTION",
            title="Request fails with TypeError",
            description="Requests return 500 with a TypeError stack trace.",
            affected_service="generic_service",
        ),
    )
    state.add_evidence(log_evidence())
    state.add_evidence(code_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is True
    assert result.retry_required is False
    assert not any("Knowledge-base evidence is missing" in item for item in result.missing_evidence)


@pytest.mark.asyncio
async def test_evidence_evaluator_allows_rca_when_expected_behavior_kb_exists() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(
        confidence_threshold=0.75,
        incident=Incident(
            incident_id="INC-BEHAVIOR",
            title="Successful responses contain wrong results",
            description="Expected behavior is unclear after deployment.",
            affected_service="generic_service",
        ),
    )
    state.add_evidence(log_evidence())
    state.add_evidence(generic_implementation_evidence())
    state.add_evidence(knowledge_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is True
    assert result.retry_required is False
    assert not any("Knowledge-base evidence is missing" in item for item in result.missing_evidence)


@pytest.mark.asyncio
async def test_evidence_evaluator_does_not_require_kb_when_kb_agent_is_unavailable() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(
        confidence_threshold=0.75,
        allowed_agent_names=[
            AgentName.LOG_INVESTIGATOR,
            AgentName.CODE_INVESTIGATOR,
            AgentName.EVIDENCE_EVALUATOR,
            AgentName.RCA_WRITER,
        ],
        incident=Incident(
            incident_id="INC-BEHAVIOR",
            title="Successful responses contain wrong results",
            description="Expected behavior is unclear after deployment.",
            affected_service="generic_service",
        ),
    )
    state.add_evidence(log_evidence())
    state.add_evidence(generic_implementation_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is True
    assert result.retry_required is False
    assert not any("Knowledge-base evidence is missing" in item for item in result.missing_evidence)


@pytest.mark.asyncio
async def test_evidence_evaluator_requests_graph_when_structural_hint_exists_after_code() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(
        incident=Incident(
            incident_id="INC-STRUCT",
            title="Reranker config value does not affect answer ranking",
            description="Answer ranking is wrong after deployment.",
            affected_service="conversational_rag",
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-structural",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content=(
                "structural_hint: which function reads RERANKING_MODEL_NAME and "
                "which request path calls rerank_documents_with_scores()?"
            ),
        )
    )
    state.add_evidence(code_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is False
    assert result.retry_required is True
    assert "Structural graph evidence is missing." in result.missing_evidence
    assert result.reason == (
        "Structural relationship evidence is needed before RCA because the incident "
        "context asks for caller/callee, config-reader, import, ownership, or "
        "class/function relationship details."
    )


@pytest.mark.asyncio
async def test_evidence_evaluator_requests_graph_even_when_replans_are_exhausted() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(max_replans=0)
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-structural",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content=(
                "structural_hint: which function reads RERANKING_MODEL_NAME and "
                "which request path calls rerank_documents_with_scores()?"
            ),
        )
    )
    state.add_evidence(code_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is False
    assert result.retry_required is True
    assert "Structural graph evidence is missing." in result.missing_evidence


@pytest.mark.asyncio
async def test_evidence_evaluator_does_not_request_graph_without_structural_signal() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(confidence_threshold=0.75)
    state.add_evidence(log_evidence())
    state.add_evidence(code_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is True
    assert "Structural graph evidence is missing." not in result.missing_evidence


@pytest.mark.asyncio
async def test_evidence_evaluator_does_not_request_graph_before_code_exists() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state()
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-structural",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content=(
                "structural_hint: which function reads RERANKING_MODEL_NAME and "
                "which request path calls rerank_documents_with_scores()?"
            ),
        )
    )

    result = await agent.run(state)

    assert result.can_write_rca is False
    assert "Implementation code evidence is missing." in result.missing_evidence
    assert (
        "Implementation code evidence is needed before structural graph investigation."
        in result.missing_evidence
    )
    assert "Structural graph evidence is missing." not in result.missing_evidence


@pytest.mark.asyncio
async def test_evidence_evaluator_allows_rca_when_structural_graph_evidence_exists() -> None:
    agent = EvidenceEvaluatorAgent()
    state = make_state(
        incident=Incident(
            incident_id="INC-STRUCT",
            title="Reranker config value does not affect answer ranking",
            description=(
                "The investigation needs to identify which function reads "
                "RERANKING_MODEL_NAME and which request path calls reranking."
            ),
            affected_service="conversational_rag",
        )
    )
    state.add_evidence(log_evidence())
    state.add_evidence(code_evidence())
    state.add_evidence(graph_evidence())

    result = await agent.run(state)

    assert result.can_write_rca is True
    assert result.retry_required is False
    assert "Structural graph evidence is missing." not in result.missing_evidence


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
        "Evidence is incomplete, but replanning is no longer available under the configured limits."
    )
