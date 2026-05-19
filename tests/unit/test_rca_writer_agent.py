from __future__ import annotations

import pytest

from bug_resolver.agents import EvidenceEvaluatorAgent, RCAWriterAgent
from bug_resolver.schemas import (
    EvidenceItem,
    EvidenceSourceType,
    Incident,
    WorkflowState,
)


def make_state() -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Summary route fails",
            description="Users get 500 errors when asking summary questions.",
            affected_service="conversational_rag",
            affected_area="summary flow",
        )
    )


def add_evidence(state: WorkflowState) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="TypeError in route_query",
            confidence=1.0,
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-code-1",
            source_type=EvidenceSourceType.CODE,
            source_name="src/rag/router.py",
            file_path="src/rag/router.py",
            line_start=40,
            line_end=45,
            content="def route_query(...): return response['output']",
            relevance_score=0.9,
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-kb-1",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name="README.md",
            content="The router returns a structured response.",
            relevance_score=0.8,
        )
    )


@pytest.mark.asyncio
async def test_rca_writer_agent_generates_report_from_dynamic_evidence() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)

    result = await RCAWriterAgent().run(state)

    assert result.report_id.startswith("RCA-")
    assert result.incident_id == "INC-001"
    assert result.title == "RCA for Summary route fails"
    assert "Users get 500 errors" in result.incident_summary
    assert result.impact == (
        "Affected service: conversational_rag. Affected area: summary flow."
    )
    assert result.evidence_ids == ["ev-log-1", "ev-code-1", "ev-kb-1"]
    assert result.confidence_score >= state.confidence_threshold
    assert result.confidence_score < 1.0
    assert result.low_confidence_warning is None
    assert result.open_questions == []
    assert result.selected_hypothesis_id == "H1"
    assert "src/rag/router.py:40-45" in result.root_cause
    assert result.log_findings == [
        "app.log shows runtime signal: TypeError in route_query"
    ]
    assert result.code_findings == [
        (
            "src/rag/router.py:40-45 shows relevant implementation behavior: "
            "def route_query(...): return response['output']"
        )
    ]
    assert result.knowledge_base_findings == [
        (
            "README.md documents expected behavior relevant to the incident: "
            "The router returns a structured response."
        )
    ]
    assert result.metadata == {"evidence_count": "3", "dynamic_workflow": "true"}


@pytest.mark.asyncio
async def test_rca_writer_agent_requires_evidence() -> None:
    state = make_state()

    with pytest.raises(ValueError, match="requires evidence before writing an RCA"):
        await RCAWriterAgent().run(state)


@pytest.mark.asyncio
async def test_rca_writer_agent_requires_evidence_evaluation() -> None:
    state = make_state()
    add_evidence(state)

    with pytest.raises(ValueError, match="requires evidence evaluation before RCA"):
        await RCAWriterAgent().run(state)
