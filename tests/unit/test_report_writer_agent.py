"""Tests for the report writer agent persistence contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.agents import ReportWriterAgent, ReportWriterInput
from bug_resolver.schemas import PatchSuggestion, RCAReport, SolutionRecommendation


class FakeReportStore:
    def __init__(self) -> None:
        self.saved_report: RCAReport | None = None
        self.saved_solution: SolutionRecommendation | None = None
        self.saved_patch_suggestion: PatchSuggestion | None = None

    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
        patch_suggestion: PatchSuggestion | None = None,
    ) -> list[Path]:
        self.saved_report = report
        self.saved_solution = solution
        self.saved_patch_suggestion = patch_suggestion

        return [
            Path("reports/incidents") / report.incident_id / "rca.md",
            Path("reports/incidents") / report.incident_id / "rca.json",
        ]

    async def get_report(self, incident_id: str) -> RCAReport | None:
        return (
            self.saved_report
            if self.saved_report and self.saved_report.incident_id == incident_id
            else None
        )


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
        open_questions=[],
    )


def build_solution_recommendation() -> SolutionRecommendation:
    return SolutionRecommendation(
        recommendation_id="SOL-001",
        incident_id="INC-001",
        rca_report_id="RCA-001",
        summary="Recommended solution based on RCA.",
        immediate_steps=["Guard access to output key."],
        long_term_steps=["Add structured output validation."],
        tests_to_add=["Add regression test."],
        monitoring_improvements=["Add structured logging."],
        risk_notes=[],
        confidence_score=0.90,
        evidence_ids=["evidence-log-001", "evidence-code-001"],
    )


def build_patch_suggestion() -> PatchSuggestion:
    return PatchSuggestion(
        suggestion_id="PATCH-001",
        incident_id="INC-001",
        rca_report_id="RCA-001",
        solution_recommendation_id="SOL-001",
        summary="Patch plan.",
        affected_files=["src/rag/llm.py"],
        behavior_changes=["Guard access to output key."],
        tests_to_add=["Add regression test."],
        validation_commands=["Run focused tests."],
        risk_notes=["Human approval is required."],
        confidence_score=0.9,
        evidence_ids=["evidence-code-001"],
    )


@pytest.mark.asyncio
async def test_report_writer_agent_saves_rca_report() -> None:
    report_store = FakeReportStore()
    agent = ReportWriterAgent(report_store=report_store)
    rca_report = build_rca_report()

    result = await agent.run(
        ReportWriterInput(
            report=rca_report,
        )
    )

    assert report_store.saved_report == rca_report
    assert report_store.saved_solution is None
    assert report_store.saved_patch_suggestion is None
    assert result == [
        Path("reports/incidents/INC-001/rca.md"),
        Path("reports/incidents/INC-001/rca.json"),
    ]


@pytest.mark.asyncio
async def test_report_writer_agent_saves_rca_report_with_solution() -> None:
    report_store = FakeReportStore()
    agent = ReportWriterAgent(report_store=report_store)
    rca_report = build_rca_report()
    solution = build_solution_recommendation()

    result = await agent.run(
        ReportWriterInput(
            report=rca_report,
            solution=solution,
        )
    )

    assert report_store.saved_report == rca_report
    assert report_store.saved_solution == solution
    assert report_store.saved_patch_suggestion is None
    assert result == [
        Path("reports/incidents/INC-001/rca.md"),
        Path("reports/incidents/INC-001/rca.json"),
    ]


@pytest.mark.asyncio
async def test_report_writer_agent_saves_patch_suggestion() -> None:
    report_store = FakeReportStore()
    agent = ReportWriterAgent(report_store=report_store)
    rca_report = build_rca_report()
    solution = build_solution_recommendation()
    patch_suggestion = build_patch_suggestion()

    await agent.run(
        ReportWriterInput(
            report=rca_report,
            solution=solution,
            patch_suggestion=patch_suggestion,
        )
    )

    assert report_store.saved_report == rca_report
    assert report_store.saved_solution == solution
    assert report_store.saved_patch_suggestion == patch_suggestion


@pytest.mark.asyncio
async def test_report_writer_agent_rejects_none_input() -> None:
    report_store = FakeReportStore()
    agent = ReportWriterAgent(report_store=report_store)

    with pytest.raises(ValueError, match="received empty input"):
        await agent.run(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_report_writer_agent_rejects_empty_written_paths() -> None:
    class EmptyReportStore(FakeReportStore):
        async def save_report(
            self,
            report: RCAReport,
            *,
            solution: SolutionRecommendation | None = None,
            patch_suggestion: PatchSuggestion | None = None,
        ) -> list[Path]:
            return []

    agent = ReportWriterAgent(report_store=EmptyReportStore())

    with pytest.raises(ValueError, match="did not write any report files"):
        await agent.run(
            ReportWriterInput(
                report=build_rca_report(),
            )
        )
