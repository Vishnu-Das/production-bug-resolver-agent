from __future__ import annotations

import pytest

from bug_resolver.agents import RCAAgent, RCAInput
from bug_resolver.schemas import (
    CodeContext,
    Hypothesis,
    Incident,
    KnowledgeContext,
    LogAnalysisResult,
    StackTraceFrame,
)
from bug_resolver.schemas.common import (
    HypothesisStatus,
    IncidentSeverity,
    IncidentStatus,
)


@pytest.mark.asyncio
async def test_rca_agent_generates_report_from_strongest_hypothesis() -> None:
    agent = RCAAgent()

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
    )

    weak_hypothesis = Hypothesis(
        hypothesis_id="HYP-LOW",
        title="Weak hypothesis",
        description="Weak description.",
        suspected_root_cause="Weak root cause.",
        supporting_evidence_ids=["evidence-low"],
        confidence_score=0.40,
        status=HypothesisStatus.PROPOSED,
        open_questions=["Need more evidence."],
    )

    strong_hypothesis = Hypothesis(
        hypothesis_id="HYP-HIGH",
        title="KeyError likely caused the incident",
        description="The logs and code indicate the output key is missing.",
        suspected_root_cause=(
            "KeyError occurred because 'output' at src/rag/llm.py:18 in route."
        ),
        supporting_evidence_ids=[
            "evidence-log-001",
            "evidence-code-001",
        ],
        confidence_score=0.90,
        status=HypothesisStatus.SUPPORTED,
    )

    code_contexts = [
        CodeContext(
            context_id="code-001",
            file_path="src/rag/llm.py",
            snippet="return response['output']",
            line_start=18,
            line_end=18,
            function_name="route",
            relevance_score=0.90,
        )
    ]

    knowledge_contexts = [
        KnowledgeContext(
            context_id="kb-001",
            document_name="README.md",
            content="Router output should be structured.",
            section_title="Routing",
            file_path="README.md",
            relevance_score=0.80,
        )
    ]

    result = await agent.run(
        RCAInput(
            incident=incident,
            log_analysis=log_analysis,
            hypotheses=[weak_hypothesis, strong_hypothesis],
            code_contexts=code_contexts,
            knowledge_contexts=knowledge_contexts,
        )
    )

    assert result.report_id.startswith("RCA-")
    assert result.incident_id == "INC-001"
    assert result.title == "RCA for Summary query fails"
    assert result.selected_hypothesis_id == "HYP-HIGH"
    assert result.root_cause == (
        "KeyError occurred because 'output' at src/rag/llm.py:18 in route."
    )
    assert result.evidence_ids == [
        "evidence-log-001",
        "evidence-code-001",
    ]
    assert result.confidence_score == 0.90
    assert result.low_confidence_warning is None

    assert "Users get 500 error" in result.incident_summary
    assert "Affected service: conversational_rag" in result.impact
    assert "Affected area: summary flow" in result.impact
    assert "KeyError: 'output'" in result.symptoms
    assert "Found KeyError: 'output'." in result.log_findings
    assert "Exception type: KeyError" in result.log_findings
    assert "Exception message: 'output'" in result.log_findings
    assert "Retrieved code context from src/rag/llm.py::route:18-18." in result.code_findings
    assert "Retrieved knowledge-base context from README.md::Routing." in result.knowledge_base_findings
    assert result.metadata == {"selected_hypothesis_status": "supported"}


@pytest.mark.asyncio
async def test_rca_agent_marks_low_confidence_report() -> None:
    agent = RCAAgent()

    incident = Incident(
        incident_id="INC-002",
        title="Chat fails",
        description="Chat endpoint fails intermittently.",
    )

    log_analysis = LogAnalysisResult(
        summary="No explicit exception or stack trace was found.",
    )

    hypothesis = Hypothesis(
        hypothesis_id="HYP-LOW",
        title="Low evidence hypothesis",
        description="Evidence is incomplete.",
        suspected_root_cause=(
            "The root cause cannot be determined confidently from the available evidence yet."
        ),
        supporting_evidence_ids=[],
        confidence_score=0.20,
        status=HypothesisStatus.PROPOSED,
        open_questions=[
            "What exact exception caused the failure?",
        ],
    )

    result = await agent.run(
        RCAInput(
            incident=incident,
            log_analysis=log_analysis,
            hypotheses=[hypothesis],
        )
    )

    assert result.confidence_score == 0.20
    assert result.low_confidence_warning == (
        "This RCA is low confidence because the selected hypothesis does not meet "
        "the confidence threshold."
    )
    assert result.open_questions == [
        "What exact exception caused the failure?",
    ]
    assert result.selected_hypothesis_id == "HYP-LOW"


@pytest.mark.asyncio
async def test_rca_agent_adds_open_question_for_low_confidence_without_questions() -> None:
    agent = RCAAgent()

    incident = Incident(
        incident_id="INC-003",
        title="Unknown failure",
        description="Unknown failure happened.",
    )

    log_analysis = LogAnalysisResult(
        summary="No explicit exception or stack trace was found.",
    )

    hypothesis = Hypothesis(
        hypothesis_id="HYP-LOW",
        title="Low evidence hypothesis",
        description="Evidence is incomplete.",
        suspected_root_cause="Unknown root cause.",
        confidence_score=0.50,
        status=HypothesisStatus.PROPOSED,
        open_questions=[],
    )

    result = await agent.run(
        RCAInput(
            incident=incident,
            log_analysis=log_analysis,
            hypotheses=[hypothesis],
        )
    )

    assert result.open_questions == [
        "What additional evidence is needed to confirm the root cause?"
    ]


@pytest.mark.asyncio
async def test_rca_agent_requires_at_least_one_hypothesis() -> None:
    incident = Incident(
        incident_id="INC-004",
        title="Missing hypotheses",
        description="No hypotheses were generated.",
    )

    log_analysis = LogAnalysisResult(
        summary="No explicit exception or stack trace was found.",
    )

    with pytest.raises(ValueError):
        RCAInput(
            incident=incident,
            log_analysis=log_analysis,
            hypotheses=[],
        )