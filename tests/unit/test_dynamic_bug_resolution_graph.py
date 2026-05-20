"""Tests for the initial LangGraph dynamic workflow skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.agents import (
    CodeInvestigatorAgent,
    EvidenceEvaluatorAgent,
    KnowledgeBaseInvestigatorAgent,
    LogInvestigatorAgent,
    RCAWriterAgent,
    ReportWriterAgent,
    SolutionRecommendationAgent,
)
from bug_resolver.rules import GuardrailEngine
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    CodeContext,
    Incident,
    InvestigationStatus,
    KnowledgeContext,
    LogEntry,
    LogLevel,
    RCAReport,
    SolutionRecommendation,
    WorkflowState,
)
from bug_resolver.workflows.dynamic_bug_resolution_graph import (
    DynamicBugResolutionGraphWorkflow,
)


class FakeIncidentProvider:
    """Return a stable incident for graph workflow tests."""

    async def get_incident(self, incident_id: str) -> Incident:
        return Incident(
            incident_id=incident_id,
            title="Summary route fails",
            description="Users get 500 errors when asking summary questions.",
            affected_service="conversational_rag",
        )


class FakeSupervisorAgent:
    """Yield predetermined supervisor decisions to keep graph tests deterministic."""

    def __init__(self, decisions: list[AgentDecision]) -> None:
        self.decisions = decisions
        self.call_count = 0
        self.seen_states: list[WorkflowState] = []

    async def run(self, state: WorkflowState) -> AgentDecision:
        self.seen_states.append(state.model_copy(deep=True))

        if self.call_count >= len(self.decisions):
            return AgentDecision(
                decision_id=f"fallback-finish-{self.call_count}",
                next_agent=AgentName.FINISH,
                reason="No more fake supervisor decisions.",
                queries=[],
                expected_evidence=[],
                should_continue=False,
            )

        decision = self.decisions[self.call_count]
        self.call_count += 1
        return decision


class FakeLogProvider:
    """Return one log entry that points toward the router failure."""

    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        return [
            LogEntry(
                log_id="log-1",
                level=LogLevel.ERROR,
                message="Application failed",
                raw=(
                    'File "src/rag/router.py", line 42, in route_query\n'
                    "TypeError: expected dict response"
                ),
                service_name="conversational_rag",
            )
        ]


class FakeCodeContextProvider:
    """Return one code context item that supports RCA generation."""

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        return [
            CodeContext(
                context_id="code-1",
                file_path="src/rag/router.py",
                function_name="route_query",
                line_start=40,
                line_end=45,
                snippet="def route_query(...): return response['output']",
                relevance_score=0.91,
            )
        ]


class EmptyKnowledgeBaseProvider:
    """Return no knowledge-base hits for this graph skeleton test."""

    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        return []


class FakeReportStore:
    """Pretend to persist generated reports and return a stable path."""

    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
    ) -> list[Path]:
        return [Path(f"reports/incidents/{report.incident_id}/rca.md")]

    async def get_report(self, incident_id: str) -> RCAReport | None:
        return None


def decision(decision_id: str, agent_name: AgentName, queries: list[str]) -> AgentDecision:
    """Build a fake supervisor decision for the requested agent."""
    return AgentDecision(
        decision_id=decision_id,
        next_agent=agent_name,
        reason=f"Route to {agent_name.value}.",
        queries=queries,
        expected_evidence=["evidence"],
        should_continue=True,
    )


def make_graph_workflow(
    supervisor: FakeSupervisorAgent,
) -> DynamicBugResolutionGraphWorkflow:
    """Create the graph workflow with deterministic local test doubles."""
    return DynamicBugResolutionGraphWorkflow(
        incident_provider=FakeIncidentProvider(),
        supervisor_agent=supervisor,  # type: ignore[arg-type]
        guardrail_engine=GuardrailEngine(),
        log_investigator_agent=LogInvestigatorAgent(FakeLogProvider()),
        code_investigator_agent=CodeInvestigatorAgent(FakeCodeContextProvider()),
        knowledge_base_investigator_agent=KnowledgeBaseInvestigatorAgent(
            EmptyKnowledgeBaseProvider()
        ),
        evidence_evaluator_agent=EvidenceEvaluatorAgent(),
        rca_writer_agent=RCAWriterAgent(),
        solution_recommendation_agent=SolutionRecommendationAgent(),
        report_writer_agent=ReportWriterAgent(FakeReportStore()),
        max_steps=12,
        max_replans=2,
        minimum_evidence_count_before_rca=2,
    )


@pytest.mark.asyncio
async def test_graph_workflow_completes_rca_solution_and_report() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
        ]
    )
    workflow = make_graph_workflow(supervisor)

    state = await workflow.run("INC-001")

    step_agents = [step.agent_name for step in state.trace.steps]

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert state.rca_report is not None
    assert state.solution_recommendation is not None
    assert state.final_report_path == Path("reports/incidents/INC-001/rca.md")
    assert step_agents[-3:] == [
        AgentName.RCA_WRITER,
        AgentName.SOLUTION_RECOMMENDER,
        AgentName.REPORT_WRITER,
    ]
    assert supervisor.call_count == 2
