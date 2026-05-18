from __future__ import annotations

from pathlib import Path

from typer.cli import state

import pytest

from bug_resolver.agents import (
    CodeContextAgent,
    ContextPlanningAgent,
    EvidenceEvaluatorAgent,
    HypothesisAgent,
    IncidentIntakeAgent,
    KnowledgeBaseAgent,
    LogAnalysisAgent,
    RCAAgent,
    ReportWriterAgent,
    SolutionRecommendationAgent,
)
from bug_resolver.providers.code.base import CodeContextProvider
from bug_resolver.providers.knowledge.base import KnowledgeBaseProvider
from bug_resolver.providers.reports.base import ReportStore
from bug_resolver.schemas import CodeContext, KnowledgeContext, LogEntry, RCAReport
from bug_resolver.schemas.common import EvidenceSourceType, LogLevel, WorkflowStatus
from bug_resolver.schemas.incident_intake import IncidentIntakeRequest
from bug_resolver.schemas.solution import SolutionRecommendation
from bug_resolver.workflows import BugResolutionWorkflow
from bug_resolver.schemas import EvidenceEvaluationResult
from bug_resolver.schemas import (
    CodeContext,
    EvidenceEvaluationResult,
    KnowledgeContext,
    LogEntry,
    RCAReport,
)


class FakeLogProvider:
    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        return [
            LogEntry(
                log_id="log-001",
                level=LogLevel.ERROR,
                message="Application error",
                raw=(
                    "Traceback (most recent call last):\n"
                    ' File "src/rag/router.py", line 42, in route_query\n'
                    " return router.route(query)\n"
                    ' File "src/rag/llm.py", line 18, in route\n'
                    " return response['output']\n"
                    "KeyError: 'output'"
                ),
                service_name="conversational_rag",
                request_id="req-123",
                trace_id="trace-456",
            )
        ]


class FakeCodeContextProvider(CodeContextProvider):
    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        return [
            CodeContext(
                context_id="code-001",
                file_path="src/rag/llm.py",
                line_start=1,
                line_end=30,
                snippet="def route(...):\n    return response['output']",
                relevance_score=0.9,
                metadata={"queries": ",".join(queries)},
            )
        ]


class FakeKnowledgeBaseProvider(KnowledgeBaseProvider):
    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        return [
            KnowledgeContext(
                context_id="kb-001",
                document_name="README.md",
                content="The app routes user queries through an LLM router.",
                relevance_score=0.8,
                metadata={"queries": ",".join(queries)},
            )
        ]


class FakeReportStore(ReportStore):
    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
    ) -> list[Path]:
        return [Path("reports/incidents/INC-001/rca.md")]

    async def get_report(self, incident_id: str) -> RCAReport | None:
        return None
    
class RetryThenPassEvidenceEvaluatorAgent:
    def __init__(self) -> None:
        self.call_count = 0

    async def run(self, report: RCAReport) -> EvidenceEvaluationResult:
        self.call_count += 1

        if self.call_count == 1:
            return EvidenceEvaluationResult(
                evaluation_id="eval-001",
                incident_id=report.incident_id,
                confidence_score=0.40,
                retry_required=True,
                missing_evidence=[
                    "Need code evidence for response['output'] access.",
                ],
                conflicting_evidence=[],
                improved_code_queries=[
                    "response output key access router llm.py",
                ],
                improved_knowledge_queries=[
                    "LLM router expected output schema",
                ],
                reason="RCA confidence is low and code evidence is incomplete.",
            )

        return EvidenceEvaluationResult(
            evaluation_id="eval-002",
            incident_id=report.incident_id,
            confidence_score=0.90,
            retry_required=False,
            missing_evidence=[],
            conflicting_evidence=[],
            improved_code_queries=[],
            improved_knowledge_queries=[],
            reason="RCA is sufficiently supported after retry.",
        )

class AlwaysRetryEvidenceEvaluatorAgent:
    def __init__(self) -> None:
        self.call_count = 0

    async def run(self, report: RCAReport) -> EvidenceEvaluationResult:
        self.call_count += 1

        return EvidenceEvaluationResult(
            evaluation_id=f"eval-{self.call_count:03d}",
            incident_id=report.incident_id,
            confidence_score=0.30,
            retry_required=True,
            missing_evidence=["Still missing strong evidence."],
            conflicting_evidence=[],
            improved_code_queries=["more code evidence"],
            improved_knowledge_queries=["more knowledge evidence"],
            reason="RCA is still weak.",
        )

@pytest.mark.asyncio
async def test_bug_resolution_workflow_runs_full_investigation() -> None:
    workflow = BugResolutionWorkflow(
        incident_intake_agent=IncidentIntakeAgent(),
        log_provider=FakeLogProvider(),
        log_analysis_agent=LogAnalysisAgent(),
        context_planning_agent=ContextPlanningAgent(),
        code_context_agent=CodeContextAgent(FakeCodeContextProvider()),
        knowledge_base_agent=KnowledgeBaseAgent(FakeKnowledgeBaseProvider()),
        hypothesis_agent=HypothesisAgent(),
        rca_agent=RCAAgent(),
        evidence_evaluator_agent=EvidenceEvaluatorAgent(),
        solution_recommendation_agent=SolutionRecommendationAgent(),
        report_writer_agent=ReportWriterAgent(FakeReportStore()),
    )

    state = await workflow.run(
        IncidentIntakeRequest(
            incident_id="INC-001",
            title="Summary query fails",
            description="Users get a 500 error while asking summary questions.",
            affected_service="conversational_rag",
        )
    )

    assert state.status == WorkflowStatus.REPORT_SAVED
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
async def test_bug_resolution_workflow_retries_when_evidence_is_weak() -> None:
    evidence_evaluator_agent = RetryThenPassEvidenceEvaluatorAgent()

    workflow = BugResolutionWorkflow(
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

    state = await workflow.run(
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
async def test_bug_resolution_workflow_stops_retry_at_max_retries() -> None:
    evidence_evaluator_agent = AlwaysRetryEvidenceEvaluatorAgent()

    workflow = BugResolutionWorkflow(
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

    state = await workflow.run(
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