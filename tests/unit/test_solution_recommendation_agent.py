from __future__ import annotations

import pytest

from bug_resolver.agents import SolutionRecommendationAgent
from bug_resolver.schemas import RCAReport


@pytest.mark.asyncio
async def test_solution_recommendation_agent_builds_recommendation_from_rca() -> None:
    agent = SolutionRecommendationAgent()

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
        evidence_ids=["evidence-log-001", "evidence-code-001"],
        confidence_score=0.90,
        confidence_reason="Confidence is high enough because evidence is present.",
        immediate_fix="Guard access to the output key before reading router response.",
        long_term_prevention="Add structured output validation for router responses.",
        tests_to_add=["Add regression test for missing output key."],
        open_questions=[],
    )

    result = await agent.run(rca_report)

    assert result.recommendation_id.startswith("SOL-")
    assert result.incident_id == "INC-001"
    assert result.rca_report_id == "RCA-001"
    assert result.summary == (
        "Recommended solution based on RCA RCA-001: "
        "KeyError occurred because 'output' was missing."
    )
    assert result.immediate_steps == [
        "Guard access to the output key before reading router response.",
        "Reproduce the incident locally using the same failure scenario.",
        "Verify the fix against the log symptoms and selected RCA evidence.",
    ]
    assert result.long_term_steps == [
        "Add structured output validation for router responses.",
        "Improve defensive handling around the failing code path.",
        "Document the expected behavior and failure mode for future incidents.",
    ]
    assert result.tests_to_add == ["Add regression test for missing output key."]
    assert result.monitoring_improvements == [
        "Add structured logging around the failing code path.",
        "Log request or trace identifiers with the error when available.",
    ]
    assert result.risk_notes == []
    assert result.confidence_score == 0.90
    assert result.evidence_ids == ["evidence-log-001", "evidence-code-001"]


@pytest.mark.asyncio
async def test_solution_recommendation_agent_uses_fallback_steps_when_rca_has_no_fix_fields() -> None:
    agent = SolutionRecommendationAgent()

    rca_report = RCAReport(
        report_id="RCA-002",
        incident_id="INC-002",
        title="RCA for Router issue",
        incident_summary="Incident INC-002: Router issue.",
        symptoms=["Router issue."],
        log_findings=["Found RuntimeError."],
        code_findings=["Retrieved code context from src/rag/router.py."],
        knowledge_base_findings=["Retrieved knowledge-base context from README.md."],
        hypotheses_considered=["HYP-001: RuntimeError caused issue."],
        selected_hypothesis_id="HYP-001",
        root_cause="RuntimeError caused issue.",
        technical_explanation="Runtime error in router.",
        evidence_ids=["evidence-log-001"],
        confidence_score=0.80,
        confidence_reason="Evidence is sufficient.",
        open_questions=[],
    )

    result = await agent.run(rca_report)

    assert result.immediate_steps[0] == (
        "Inspect the failing code path identified in the RCA and apply a scoped fix."
    )
    assert "Add a regression test that reproduces the incident." in result.tests_to_add
    assert "Add a unit test for the suspected failing code path." in result.tests_to_add


@pytest.mark.asyncio
async def test_solution_recommendation_agent_adds_risk_notes_for_low_confidence_rca() -> None:
    agent = SolutionRecommendationAgent()

    rca_report = RCAReport(
        report_id="RCA-003",
        incident_id="INC-003",
        title="RCA for Unknown failure",
        incident_summary="Incident INC-003: Unknown failure.",
        symptoms=["Unknown failure."],
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
        open_questions=["What exact exception caused the failure?"],
        low_confidence_warning=(
            "This RCA is low confidence because the selected hypothesis does not meet "
            "the confidence threshold."
        ),
    )

    result = await agent.run(rca_report)

    assert result.risk_notes == [
        (
            "This RCA is low confidence because the selected hypothesis does not meet "
            "the confidence threshold."
        ),
        (
            "Some open questions remain, so the recommendation should be validated "
            "before implementation."
        ),
        (
            "No supporting evidence IDs are attached to the RCA, so confidence in the "
            "recommendation is limited."
        ),
        "RCA confidence is below the production threshold of 0.75.",
    ]

    assert (
        "Capture additional diagnostic logs because the current RCA is low confidence."
        in result.monitoring_improvements
    )
    assert result.confidence_score == 0.20
    assert result.evidence_ids == []