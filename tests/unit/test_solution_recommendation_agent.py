from __future__ import annotations

import pytest

from bug_resolver.agents import (
    SolutionRecommendationAgent,
    SolutionRecommendationOutput,
)
from bug_resolver.schemas import RCAReport


class FakeSolutionLLM:
    def __init__(
        self,
        output: SolutionRecommendationOutput | None = None,
        *,
        should_fail: bool = False,
    ) -> None:
        self.output = output
        self.should_fail = should_fail
        self.prompt: str | None = None
        self.system_prompt: str | None = None

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        raise AssertionError("SolutionRecommendationAgent should request structured output")

    async def generate_structured(
        self,
        prompt: str,
        output_schema,
        *,
        system_prompt: str | None = None,
    ):
        self.prompt = prompt
        self.system_prompt = system_prompt

        if self.should_fail:
            raise ValueError("LLM failed")

        assert output_schema is SolutionRecommendationOutput
        assert self.output is not None
        return self.output


def build_rca_report() -> RCAReport:
    return RCAReport(
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


@pytest.mark.asyncio
async def test_solution_recommendation_agent_builds_recommendation_from_rca() -> None:
    agent = SolutionRecommendationAgent()

    rca_report = build_rca_report()

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
        "Add input and output contract checks around the implicated code path.",
        "Document the expected behavior and failure mode for future incidents.",
    ]
    assert result.tests_to_add == ["Add regression test for missing output key."]
    assert result.monitoring_improvements == [
        "Add structured logging around the implicated code path.",
        "Log request or trace identifiers with the error when available.",
    ]
    assert result.risk_notes == []
    assert result.confidence_score == 0.90
    assert result.evidence_ids == ["evidence-log-001", "evidence-code-001"]


@pytest.mark.asyncio
async def test_solution_recommendation_agent_can_generate_llm_backed_recommendation() -> None:
    rca_report = build_rca_report()
    llm = FakeSolutionLLM(
        SolutionRecommendationOutput(
            summary="LLM recommendation: guard router response access.",
            immediate_steps=[
                "Validate the router response contains the expected output key.",
                "Reproduce the failing summary request.",
            ],
            long_term_steps=[
                "Use structured response contracts for router outputs.",
            ],
            tests_to_add=["Add missing output key regression test."],
            monitoring_improvements=["Log invalid router response shape."],
            risk_notes=["Validate against production-like router payloads."],
            confidence_score=0.85,
            evidence_ids=["evidence-log-001", "evidence-code-001"],
        )
    )

    result = await SolutionRecommendationAgent(llm_client=llm).run(rca_report)

    assert result.recommendation_id.startswith("SOL-")
    assert result.incident_id == "INC-001"
    assert result.rca_report_id == "RCA-001"
    assert result.summary == "LLM recommendation: guard router response access."
    assert result.confidence_score == 0.85
    assert result.evidence_ids == ["evidence-log-001", "evidence-code-001"]
    assert llm.prompt is not None
    assert "Allowed evidence IDs: evidence-log-001, evidence-code-001" in llm.prompt


@pytest.mark.asyncio
async def test_solution_recommendation_agent_falls_back_when_llm_fails() -> None:
    rca_report = build_rca_report()
    llm = FakeSolutionLLM(should_fail=True)

    result = await SolutionRecommendationAgent(llm_client=llm).run(rca_report)

    assert result.summary == (
        "Recommended solution based on RCA RCA-001: "
        "KeyError occurred because 'output' was missing."
    )
    assert result.confidence_score == 0.90


@pytest.mark.asyncio
async def test_solution_recommendation_agent_falls_back_for_unknown_evidence() -> None:
    rca_report = build_rca_report()
    llm = FakeSolutionLLM(
        SolutionRecommendationOutput(
            summary="Bad recommendation.",
            immediate_steps=["Do something."],
            long_term_steps=[],
            tests_to_add=[],
            monitoring_improvements=[],
            risk_notes=[],
            confidence_score=0.85,
            evidence_ids=["not-collected"],
        )
    )

    result = await SolutionRecommendationAgent(llm_client=llm).run(rca_report)

    assert result.summary.startswith("Recommended solution based on RCA RCA-001")
    assert result.evidence_ids == ["evidence-log-001", "evidence-code-001"]


@pytest.mark.asyncio
async def test_solution_recommendation_agent_falls_back_when_confidence_exceeds_rca() -> None:
    rca_report = build_rca_report()
    llm = FakeSolutionLLM(
        SolutionRecommendationOutput(
            summary="Overconfident recommendation.",
            immediate_steps=["Do something."],
            long_term_steps=[],
            tests_to_add=[],
            monitoring_improvements=[],
            risk_notes=[],
            confidence_score=1.0,
            evidence_ids=["evidence-log-001"],
        )
    )

    result = await SolutionRecommendationAgent(llm_client=llm).run(rca_report)

    assert result.summary.startswith("Recommended solution based on RCA RCA-001")
    assert result.confidence_score == 0.90


@pytest.mark.asyncio
async def test_solution_recommendation_agent_falls_back_when_llm_claims_fix_was_done() -> None:
    rca_report = build_rca_report()
    llm = FakeSolutionLLM(
        SolutionRecommendationOutput(
            summary="The issue has been fixed.",
            immediate_steps=["We fixed the router output handling."],
            long_term_steps=["Add contracts."],
            tests_to_add=["Add regression test."],
            monitoring_improvements=["Log invalid router response shape."],
            risk_notes=[],
            confidence_score=0.85,
            evidence_ids=["evidence-log-001"],
        )
    )

    result = await SolutionRecommendationAgent(llm_client=llm).run(rca_report)

    assert result.summary.startswith("Recommended solution based on RCA RCA-001")
    assert result.confidence_score == 0.90


@pytest.mark.asyncio
async def test_solution_recommendation_agent_falls_back_for_unbalanced_inline_code() -> None:
    rca_report = build_rca_report()
    llm = FakeSolutionLLM(
        SolutionRecommendationOutput(
            summary="Fix `ValueError: invalid strategy without closing marker.",
            immediate_steps=["Validate router output."],
            long_term_steps=["Add contracts."],
            tests_to_add=["Add regression test."],
            monitoring_improvements=["Log invalid router response shape."],
            risk_notes=[],
            confidence_score=0.85,
            evidence_ids=["evidence-log-001"],
        )
    )

    result = await SolutionRecommendationAgent(llm_client=llm).run(rca_report)

    assert result.summary.startswith("Recommended solution based on RCA RCA-001")
    assert result.confidence_score == 0.90


@pytest.mark.asyncio
async def test_solution_recommendation_agent_falls_back_without_tests() -> None:
    rca_report = build_rca_report()
    llm = FakeSolutionLLM(
        SolutionRecommendationOutput(
            summary="Recommendation.",
            immediate_steps=["Validate router output handling."],
            long_term_steps=["Add contracts."],
            tests_to_add=[],
            monitoring_improvements=["Log invalid router response shape."],
            risk_notes=[],
            confidence_score=0.85,
            evidence_ids=["evidence-log-001"],
        )
    )

    result = await SolutionRecommendationAgent(llm_client=llm).run(rca_report)

    assert result.summary.startswith("Recommended solution based on RCA RCA-001")
    assert result.tests_to_add == ["Add regression test for missing output key."]


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
