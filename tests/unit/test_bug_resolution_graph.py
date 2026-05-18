from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.agents import (
    CodeContextAgent,
    ContextPlanningAgent,
    HypothesisAgent,
    IncidentIntakeAgent,
    KnowledgeBaseAgent,
    LogAnalysisAgent,
    RCAAgent,
    ReportWriterAgent,
    SolutionRecommendationAgent,
)
from bug_resolver.schemas.common import WorkflowStatus
from bug_resolver.schemas.incident_intake import IncidentIntakeRequest
from bug_resolver.workflows import BugResolutionGraph
from workflow_fakes import (
    AlwaysRetryEvidenceEvaluatorAgent,
    FakeCodeContextProvider,
    FakeKnowledgeBaseProvider,
    FakeLogProvider,
    FakeReportStore,
    RetryThenPassEvidenceEvaluatorAgent,
)


@pytest.mark.asyncio
async def test_bug_resolution_graph_runs_full_investigation() -> None:
    evidence_evaluator_agent = RetryThenPassEvidenceEvaluatorAgent()

    graph = BugResolutionGraph(
        incident_intake_agent=IncidentIntakeAgent(),
        log_provider=FakeLogProvider(),
        log_analysis_agent=LogAnalysisAgent(),
        context_planning_agent=ContextPlanningAgent(),
        code_context_agent=CodeContextAgent(FakeCodeContextProvider()),
        knowledge_base_agent=KnowledgeBaseAgent(FakeKnowledgeBaseProvider()),
        hypothesis_agent=HypothesisAgent(),
        rca_agent=RCAAgent(),
        evidence_evaluator_agent=evidence_evaluator_agent,  # type: ignore[arg-type]
        solution_recommendation_agent=SolutionRecommendationAgent(),
        report_writer_agent=ReportWriterAgent(FakeReportStore()),
        max_retries=2,
        confidence_threshold=0.75,
    )

    state = await graph.run(
        IncidentIntakeRequest(
            incident_id="INC-001",
            title="Summary query fails",
            description="Users get a 500 error while asking summary questions.",
            affected_service="conversational_rag",
        )
    )

    assert state.status == WorkflowStatus.REPORT_SAVED
    assert state.incident is not None
    assert state.incident.incident_id == "INC-001"
    assert len(state.parsed_logs) == 1
    assert state.log_analysis is not None
    assert state.context_plan is not None
    assert state.code_context
    assert state.knowledge_context
    assert state.hypotheses
    assert state.rca_report is not None
    assert state.evidence_evaluation is not None
    assert state.solution_recommendation is not None
    assert state.final_report_path == Path("reports/incidents/INC-001/rca.md")
    assert state.errors == []


@pytest.mark.asyncio
async def test_bug_resolution_graph_retries_when_evidence_is_weak() -> None:
    evidence_evaluator_agent = RetryThenPassEvidenceEvaluatorAgent()

    graph = BugResolutionGraph(
        incident_intake_agent=IncidentIntakeAgent(),
        log_provider=FakeLogProvider(),
        log_analysis_agent=LogAnalysisAgent(),
        context_planning_agent=ContextPlanningAgent(),
        code_context_agent=CodeContextAgent(FakeCodeContextProvider()),
        knowledge_base_agent=KnowledgeBaseAgent(FakeKnowledgeBaseProvider()),
        hypothesis_agent=HypothesisAgent(),
        rca_agent=RCAAgent(),
        evidence_evaluator_agent=evidence_evaluator_agent,  # type: ignore[arg-type]
        solution_recommendation_agent=SolutionRecommendationAgent(),
        report_writer_agent=ReportWriterAgent(FakeReportStore()),
        max_retries=2,
        confidence_threshold=0.75,
    )

    state = await graph.run(
        IncidentIntakeRequest(
            incident_id="INC-001",
            title="Summary query fails",
            description="Users get a 500 error while asking summary questions.",
            affected_service="conversational_rag",
        )
    )

    assert state.status == WorkflowStatus.REPORT_SAVED
    assert state.retry_count == 1
    assert evidence_evaluator_agent.call_count == 2
    assert state.evidence_evaluation is not None
    assert state.evidence_evaluation.confidence_score == 0.90
    assert state.evidence_evaluation.retry_required is False
    assert state.context_plan is not None
    assert state.context_plan.retry_reason == (
        "RCA confidence is low and code evidence is incomplete."
    )
    assert (
        "Need code evidence for response['output'] access."
        in state.context_plan.missing_evidence_hints
    )
    assert state.errors == []


@pytest.mark.asyncio
async def test_bug_resolution_graph_stops_retry_at_max_retries() -> None:
    evidence_evaluator_agent = AlwaysRetryEvidenceEvaluatorAgent()

    graph = BugResolutionGraph(
        incident_intake_agent=IncidentIntakeAgent(),
        log_provider=FakeLogProvider(),
        log_analysis_agent=LogAnalysisAgent(),
        context_planning_agent=ContextPlanningAgent(),
        code_context_agent=CodeContextAgent(FakeCodeContextProvider()),
        knowledge_base_agent=KnowledgeBaseAgent(FakeKnowledgeBaseProvider()),
        hypothesis_agent=HypothesisAgent(),
        rca_agent=RCAAgent(),
        evidence_evaluator_agent=evidence_evaluator_agent,  # type: ignore[arg-type]
        solution_recommendation_agent=SolutionRecommendationAgent(),
        report_writer_agent=ReportWriterAgent(FakeReportStore()),
        max_retries=2,
        confidence_threshold=0.75,
    )

    state = await graph.run(
        IncidentIntakeRequest(
            incident_id="INC-001",
            title="Summary query fails",
            description="Users get a 500 error while asking summary questions.",
            affected_service="conversational_rag",
        )
    )

    assert state.status == WorkflowStatus.REPORT_SAVED
    assert state.retry_count == 2
    assert evidence_evaluator_agent.call_count == 3
    assert state.evidence_evaluation is not None
    assert state.evidence_evaluation.retry_required is True
    assert state.evidence_evaluation.confidence_score == 0.30
    assert state.solution_recommendation is not None
    assert state.final_report_path == Path("reports/incidents/INC-001/rca.md")
    assert state.errors == []