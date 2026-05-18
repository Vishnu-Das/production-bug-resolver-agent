from __future__ import annotations

import pytest

from bug_resolver.agents import EvidenceEvaluatorAgent
from bug_resolver.schemas import RCAReport


@pytest.mark.asyncio
async def test_evidence_evaluator_agent_accepts_supported_rca() -> None:
    agent = EvidenceEvaluatorAgent()

    rca_report = RCAReport(
        report_id="RCA-001",
        incident_id="INC-001",
        title="RCA for Summary query fails",
        incident_summary="Incident INC-001: Users get 500 error.",
        symptoms=["Users get 500 error.", "KeyError: 'output'"],
        log_findings=["Found KeyError: 'output'."],
        code_findings=["Retrieved code context from src/rag/llm.py::route:18-18."],
        knowledge_base_findings=["Retrieved knowledge-base context from README.md::Routing."],
        hypotheses_considered=["HYP-001: KeyError likely caused the incident."],
        selected_hypothesis_id="HYP-001",
        root_cause="KeyError occurred because 'output' was missing.",
        technical_explanation="The runtime evidence points to src/rag/llm.py:18.",
        evidence_ids=["evidence-log-001", "evidence-code-001", "evidence-kb-001"],
        confidence_score=0.90,
        confidence_reason="Confidence is high enough because evidence is present.",
        open_questions=[],
    )

    result = await agent.run(rca_report)

    assert result.evaluation_id.startswith("EVAL-")
    assert result.incident_id == "INC-001"
    assert result.confidence_score == 0.90
    assert result.retry_required is False
    assert result.missing_evidence == []
    assert result.conflicting_evidence == []
    assert result.improved_code_queries == []
    assert result.improved_knowledge_queries == []
    assert result.reason == (
        "Retry is not required because the RCA confidence meets the threshold "
        "and required evidence is present."
    )


@pytest.mark.asyncio
async def test_evidence_evaluator_agent_requires_retry_for_low_confidence_rca() -> None:
    agent = EvidenceEvaluatorAgent()

    rca_report = RCAReport(
        report_id="RCA-002",
        incident_id="INC-002",
        title="RCA for Chat fails",
        incident_summary="Incident INC-002: Chat endpoint fails intermittently.",
        symptoms=["Chat endpoint fails intermittently."],
        log_findings=["No explicit exception or stack trace was found."],
        code_findings=[],
        knowledge_base_findings=[],
        hypotheses_considered=["HYP-LOW: Low evidence hypothesis."],
        selected_hypothesis_id="HYP-LOW",
        root_cause="The root cause cannot be determined confidently.",
        technical_explanation="Evidence is incomplete.",
        evidence_ids=[],
        confidence_score=0.20,
        confidence_reason="Confidence is below threshold.",
        open_questions=[
            "What exact exception caused the failure?",
            "Which implementation code path maps to the log failure?",
            "What is the expected behavior according to project documentation?",
        ],
        low_confidence_warning=(
            "This RCA is low confidence because the selected hypothesis does not meet "
            "the confidence threshold."
        ),
    )

    result = await agent.run(rca_report)

    assert result.retry_required is True
    assert "RCA has no supporting evidence IDs." in result.missing_evidence
    assert "RCA has no code findings." in result.missing_evidence
    assert "RCA has no knowledge-base findings." in result.missing_evidence
    assert "RCA confidence is below threshold." in result.missing_evidence
    assert "RCA still has open questions." in result.missing_evidence

    assert "The root cause cannot be determined confidently." in result.improved_code_queries
    assert "Chat endpoint fails intermittently." in result.improved_code_queries
    assert "Which implementation code path maps to the log failure?" in result.improved_code_queries
    assert "Find implementation code path related to the RCA root cause." in result.improved_code_queries

    assert "Chat endpoint fails intermittently." in result.improved_knowledge_queries
    assert (
        "What is the expected behavior according to project documentation?"
        in result.improved_knowledge_queries
    )
    assert (
        "Find expected behavior or design documentation for this incident."
        in result.improved_knowledge_queries
    )

    assert result.reason == (
        "Retry is required because the RCA is not sufficiently supported by "
        "the available evidence."
    )


@pytest.mark.asyncio
async def test_evidence_evaluator_agent_requires_retry_when_evidence_ids_missing() -> None:
    agent = EvidenceEvaluatorAgent()

    rca_report = RCAReport(
        report_id="RCA-003",
        incident_id="INC-003",
        title="RCA for Router issue",
        incident_summary="Incident INC-003: Router issue.",
        symptoms=["Router issue."],
        log_findings=["Found RuntimeError."],
        code_findings=["Retrieved code context from src/rag/router.py."],
        knowledge_base_findings=["Retrieved knowledge-base context from README.md."],
        hypotheses_considered=["HYP-001: RuntimeError caused issue."],
        selected_hypothesis_id="HYP-001",
        root_cause="RuntimeError caused issue.",
        technical_explanation="Runtime error in router.",
        evidence_ids=[],
        confidence_score=0.90,
        confidence_reason="Confidence says high but evidence IDs are missing.",
        open_questions=[],
    )

    result = await agent.run(rca_report)

    assert result.retry_required is True
    assert result.missing_evidence == ["RCA has no supporting evidence IDs."]
    assert result.improved_code_queries != []
    assert result.improved_knowledge_queries != []


@pytest.mark.asyncio
async def test_evidence_evaluator_agent_requires_retry_when_code_findings_missing() -> None:
    agent = EvidenceEvaluatorAgent()

    rca_report = RCAReport(
        report_id="RCA-004",
        incident_id="INC-004",
        title="RCA for Missing code context",
        incident_summary="Incident INC-004: Missing code context.",
        symptoms=["Missing code context."],
        log_findings=["Found KeyError."],
        code_findings=[],
        knowledge_base_findings=["Retrieved knowledge-base context from README.md."],
        hypotheses_considered=["HYP-001: KeyError caused issue."],
        selected_hypothesis_id="HYP-001",
        root_cause="KeyError caused issue.",
        technical_explanation="KeyError happened.",
        evidence_ids=["evidence-log-001"],
        confidence_score=0.90,
        confidence_reason="Confidence says high but code context is missing.",
        open_questions=[],
    )

    result = await agent.run(rca_report)

    assert result.retry_required is True
    assert result.missing_evidence == ["RCA has no code findings."]
    assert "Find implementation code path related to the RCA root cause." in result.improved_code_queries