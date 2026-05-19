"""Tests for supervisor-led workflow routing, guardrails, and finalization."""

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
    AgentRunStatus,
    CodeContext,
    EvidenceSourceType,
    Incident,
    InvestigationStatus,
    KnowledgeContext,
    LogEntry,
    LogLevel,
    RCAReport,
    SolutionRecommendation,
    WorkflowState,
)
from bug_resolver.workflows import DynamicBugResolutionWorkflow


class FakeIncidentProvider:
    async def get_incident(self, incident_id: str) -> Incident:
        return Incident(
            incident_id=incident_id,
            title="Summary route fails",
            description="Users get 500 errors when asking summary questions.",
            affected_service="conversational_rag",
        )


class FakeSupervisorAgent:
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


class FakeKnowledgeBaseProvider:
    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        return [
            KnowledgeContext(
                context_id="kb-1",
                document_name="README.md",
                section_title="Routing",
                content="The router returns a structured response.",
                relevance_score=0.82,
            )
        ]


class FakeReportStore:
    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
    ) -> list[Path]:
        return [Path(f"reports/incidents/{report.incident_id}/rca.md")]

    async def get_report(self, incident_id: str) -> RCAReport | None:
        return None


def decision(
    decision_id: str,
    agent_name: AgentName,
    queries: list[str] | None = None,
    *,
    should_continue: bool = True,
) -> AgentDecision:
    return AgentDecision(
        decision_id=decision_id,
        next_agent=agent_name,
        reason=f"Route to {agent_name.value}.",
        queries=queries or [agent_name.value],
        expected_evidence=["evidence"],
        should_continue=should_continue,
    )


def make_workflow(supervisor: FakeSupervisorAgent) -> DynamicBugResolutionWorkflow:
    return DynamicBugResolutionWorkflow(
        incident_provider=FakeIncidentProvider(),
        supervisor_agent=supervisor,  # type: ignore[arg-type]
        guardrail_engine=GuardrailEngine(),
        log_investigator_agent=LogInvestigatorAgent(FakeLogProvider()),
        code_investigator_agent=CodeInvestigatorAgent(FakeCodeContextProvider()),
        knowledge_base_investigator_agent=KnowledgeBaseInvestigatorAgent(
            FakeKnowledgeBaseProvider()
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
async def test_dynamic_workflow_routes_to_selected_specialists_and_evaluates_evidence() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
        ]
    )
    workflow = make_workflow(supervisor)

    state = await workflow.run("INC-001")

    step_agents = [step.agent_name for step in state.trace.steps]

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert AgentName.LOG_INVESTIGATOR in step_agents
    assert AgentName.CODE_INVESTIGATOR in step_agents
    assert AgentName.EVIDENCE_EVALUATOR in step_agents
    assert AgentName.RCA_WRITER in step_agents
    assert AgentName.SOLUTION_RECOMMENDER in step_agents
    assert AgentName.REPORT_WRITER in step_agents

    assert step_agents[-3:] == [
        AgentName.RCA_WRITER,
        AgentName.SOLUTION_RECOMMENDER,
        AgentName.REPORT_WRITER,
    ]

    assert len(state.evidence_items) >= 2
    assert {evidence.source_type for evidence in state.evidence_items}.issuperset(
        {
            EvidenceSourceType.LOG,
            EvidenceSourceType.CODE,
        }
    )
    assert state.evidence_evaluation is not None
    assert state.evidence_evaluation.can_write_rca is True
    assert supervisor.call_count == 2


@pytest.mark.asyncio
async def test_dynamic_workflow_records_guardrail_blocked_decision() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.RCA_WRITER),
            decision(
                "decision-2",
                AgentName.FINISH,
                should_continue=False,
            ),
        ]
    )
    workflow = make_workflow(supervisor)

    state = await workflow.run("INC-001")

    assert state.low_confidence is False
    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert len(state.trace.guardrail_decisions) >= 2
    assert state.trace.guardrail_decisions[0].allowed is False
    assert state.trace.guardrail_decisions[0].fallback_next_agent == (AgentName.LOG_INVESTIGATOR)
    assert "runtime_evidence_required_first" in (state.trace.guardrail_decisions[0].violated_rules)
    assert "minimum_evidence_not_met_for_rca" in (state.trace.guardrail_decisions[0].violated_rules)

    assert state.trace.steps[0].run_status == AgentRunStatus.BLOCKED
    assert state.trace.steps[1].agent_name == AgentName.LOG_INVESTIGATOR
    assert state.trace.steps[1].run_status == AgentRunStatus.SUCCEEDED
    assert len(state.evidence_items) >= 1
    assert any(
        step.agent_name == AgentName.CODE_INVESTIGATOR
        and step.run_status == AgentRunStatus.SUCCEEDED
        for step in state.trace.steps
    )


@pytest.mark.asyncio
async def test_dynamic_workflow_recovers_from_early_finish_decision() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision(
                "decision-1",
                AgentName.FINISH,
                should_continue=False,
            ),
            decision(
                "decision-2",
                AgentName.FINISH,
                should_continue=False,
            ),
        ]
    )
    workflow = make_workflow(supervisor)

    workflow_state = await workflow.run("INC-001")

    assert workflow_state.investigation_status == InvestigationStatus.COMPLETED
    assert workflow_state.trace.guardrail_decisions[0].allowed is False
    assert "runtime_evidence_required_first" in (
        workflow_state.trace.guardrail_decisions[0].violated_rules
    )
    assert "finish_requires_report_or_low_confidence" in (
        workflow_state.trace.guardrail_decisions[0].violated_rules
    )
    assert workflow_state.trace.guardrail_decisions[0].fallback_next_agent == (
        AgentName.LOG_INVESTIGATOR
    )
    assert workflow_state.trace.steps[1].agent_name == AgentName.LOG_INVESTIGATOR
    assert len(workflow_state.evidence_items) >= 1
    assert any(
        step.agent_name == AgentName.CODE_INVESTIGATOR
        and step.run_status == AgentRunStatus.SUCCEEDED
        for step in workflow_state.trace.steps
    )


@pytest.mark.asyncio
async def test_dynamic_workflow_runs_final_rca_solution_and_report_routes() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
        ]
    )
    workflow = make_workflow(supervisor)

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


@pytest.mark.asyncio
async def test_dynamic_workflow_falls_back_to_code_when_supervisor_repeats_logs() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.KNOWLEDGE_BASE_INVESTIGATOR, ["router docs"]),
            decision("decision-3", AgentName.LOG_INVESTIGATOR, ["more INC-001 logs"]),
        ]
    )
    workflow = make_workflow(supervisor)

    state = await workflow.run("INC-001")

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert any(
        "missing_code_evidence_should_route_to_code" in guardrail_decision.violated_rules
        for guardrail_decision in state.trace.guardrail_decisions
    )
    assert any(
        step.agent_name == AgentName.CODE_INVESTIGATOR
        and step.run_status == AgentRunStatus.SUCCEEDED
        for step in state.trace.steps
    )
    assert state.evidence_evaluation is not None
    assert state.evidence_evaluation.can_write_rca is True
