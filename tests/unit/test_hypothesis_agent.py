from __future__ import annotations

import pytest

from bug_resolver.agents import HypothesisAgent, HypothesisInput
from bug_resolver.schemas import (
    CodeContext,
    EvidenceItem,
    Incident,
    KnowledgeContext,
    LogAnalysisResult,
    StackTraceFrame,
)
from bug_resolver.schemas.common import (
    EvidenceSourceType,
    HypothesisStatus,
    IncidentSeverity,
    IncidentStatus,
)


@pytest.mark.asyncio
async def test_hypothesis_agent_generates_supported_hypothesis_from_full_evidence() -> None:
    agent = HypothesisAgent()

    incident = Incident(
        incident_id="INC-001",
        title="Summary query fails",
        description="Users get 500 error while asking document summary questions.",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.NEW,
        affected_service="conversational_rag",
        affected_area="summary flow",
    )

    log_analysis = LogAnalysisResult(
        summary="Found KeyError: 'output'.",
        exception_type="KeyError",
        exception_message="'output'",
        stack_trace=[
            StackTraceFrame(
                file_path="src/rag/llm.py",
                line_number=18,
                function_name="route",
                raw_frame='File "src/rag/llm.py", line 18, in route',
            )
        ],
        suspected_file_paths=["src/rag/llm.py"],
        suspected_function_names=["route"],
        likely_failure_point="src/rag/llm.py:18 in route",
        evidence_items=[
            EvidenceItem(
                evidence_id="evidence-log-001",
                source_type=EvidenceSourceType.LOG,
                source_name="log-001",
                content="KeyError: 'output'",
                confidence=1.0,
            )
        ],
    )

    code_contexts = [
        CodeContext(
            context_id="code-001",
            file_path="src/rag/llm.py",
            snippet="return response['output']",
            line_start=18,
            line_end=18,
            function_name="route",
            retrieval_query="KeyError output route",
            relevance_score=0.90,
        )
    ]

    knowledge_contexts = [
        KnowledgeContext(
            context_id="kb-001",
            document_name="README.md",
            content="The router should return structured output for downstream routing.",
            section_title="Routing",
            file_path="README.md",
            retrieval_query="structured output expected behavior",
            relevance_score=0.80,
        )
    ]

    result = await agent.run(
        HypothesisInput(
            incident=incident,
            log_analysis=log_analysis,
            code_contexts=code_contexts,
            knowledge_contexts=knowledge_contexts,
        )
    )

    assert len(result) == 1

    hypothesis = result[0]

    assert hypothesis.hypothesis_id.startswith("HYP-")
    assert hypothesis.title == "KeyError likely caused the incident"
    assert "Summary query fails" in hypothesis.description
    assert "KeyError" in hypothesis.description
    assert "'output'" in hypothesis.description
    assert "src/rag/llm.py:18 in route" in hypothesis.description

    assert hypothesis.suspected_root_cause == (
        "KeyError occurred because 'output' at src/rag/llm.py:18 in route."
    )

    assert hypothesis.supporting_evidence_ids == [
        "evidence-log-001",
        "evidence-code-001",
        "evidence-kb-001",
    ]
    assert hypothesis.contradicting_evidence_ids == []
    assert hypothesis.confidence_score == 0.95
    assert hypothesis.status == HypothesisStatus.SUPPORTED
    assert hypothesis.open_questions == []


@pytest.mark.asyncio
async def test_hypothesis_agent_marks_low_evidence_hypothesis_as_proposed() -> None:
    agent = HypothesisAgent()

    incident = Incident(
        incident_id="INC-002",
        title="Chat fails",
        description="Chat endpoint fails intermittently.",
    )

    log_analysis = LogAnalysisResult(
        summary="No explicit exception or stack trace was found.",
    )

    result = await agent.run(
        HypothesisInput(
            incident=incident,
            log_analysis=log_analysis,
        )
    )

    hypothesis = result[0]

    assert hypothesis.status == HypothesisStatus.PROPOSED
    assert hypothesis.confidence_score == 0.20
    assert hypothesis.supporting_evidence_ids == []
    assert hypothesis.suspected_root_cause == (
        "The root cause cannot be determined confidently from the available evidence yet."
    )

    assert "What exact exception type caused the failure?" in hypothesis.open_questions
    assert "What exact exception message was emitted?" in hypothesis.open_questions
    assert "Which source file and function produced the failure?" in hypothesis.open_questions
    assert "Which implementation code path maps to the log failure?" in hypothesis.open_questions
    assert (
        "What is the expected behavior according to project documentation?"
        in hypothesis.open_questions
    )


@pytest.mark.asyncio
async def test_hypothesis_agent_uses_code_context_when_exception_is_missing() -> None:
    agent = HypothesisAgent()

    incident = Incident(
        incident_id="INC-003",
        title="Routing issue",
        description="Routing fails for summary questions.",
    )

    log_analysis = LogAnalysisResult(
        summary="No explicit exception was found.",
    )

    code_contexts = [
        CodeContext(
            context_id="code-001",
            file_path="src/rag/router.py",
            snippet="def route_query(query): ...",
            function_name="route_query",
            relevance_score=0.70,
        )
    ]

    result = await agent.run(
        HypothesisInput(
            incident=incident,
            log_analysis=log_analysis,
            code_contexts=code_contexts,
        )
    )

    hypothesis = result[0]

    assert hypothesis.suspected_root_cause == (
        "The issue is likely related to the retrieved implementation context "
        "in src/rag/router.py::route_query."
    )
    assert hypothesis.supporting_evidence_ids == ["evidence-code-001"]
    assert hypothesis.confidence_score == 0.40


@pytest.mark.asyncio
async def test_hypothesis_agent_deduplicates_supporting_evidence_ids() -> None:
    agent = HypothesisAgent()

    incident = Incident(
        incident_id="INC-004",
        title="Duplicate evidence",
        description="Testing duplicate evidence handling.",
    )

    log_analysis = LogAnalysisResult(
        summary="Found ValueError.",
        evidence_items=[
            EvidenceItem(
                evidence_id="same-evidence",
                source_type=EvidenceSourceType.LOG,
                source_name="log-001",
                content="ValueError",
            ),
            EvidenceItem(
                evidence_id="same-evidence",
                source_type=EvidenceSourceType.LOG,
                source_name="log-002",
                content="ValueError again",
            ),
        ],
    )

    result = await agent.run(
        HypothesisInput(
            incident=incident,
            log_analysis=log_analysis,
        )
    )

    assert result[0].supporting_evidence_ids == ["same-evidence"]