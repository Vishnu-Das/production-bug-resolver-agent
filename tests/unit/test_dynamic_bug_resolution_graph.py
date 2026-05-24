"""Tests for the initial LangGraph dynamic workflow skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.agents import (
    CodeGraphInvestigatorAgent,
    CodeInvestigatorAgent,
    EvidenceEvaluatorAgent,
    HistoricalRCAInvestigatorAgent,
    KnowledgeBaseInvestigatorAgent,
    LogInvestigatorAgent,
    PatchGeneratorAgent,
    PatchSuggestionAgent,
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
    CodeGraphContext,
    EvidenceEvaluationResult,
    EvidenceSourceType,
    FilePatch,
    HistoricalRCAContext,
    Incident,
    InvestigationStatus,
    KnowledgeContext,
    LogEntry,
    LogLevel,
    PatchSuggestion,
    PatchGenerationResult,
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


class BehaviorMismatchIncidentProvider:
    """Return a generic wrong-but-successful behavior incident."""

    async def get_incident(self, incident_id: str) -> Incident:
        return Incident(
            incident_id=incident_id,
            title="Successful responses contain wrong results",
            description=(
                "The service still returns successful responses, but users report "
                "wrong results and expected behavior is unclear after deployment."
            ),
            affected_service="generic_service",
        )


class RecurringIncidentProvider:
    """Return a generic incident that explicitly references recurrence."""

    async def get_incident(self, incident_id: str) -> Incident:
        return Incident(
            incident_id=incident_id,
            title="Duplicate records are happening again",
            description="This looks like a repeat incident similar to a previous RCA.",
            affected_service="generic_service",
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


class StructuralHintLogProvider:
    """Return log evidence that explicitly asks for structural relationships."""

    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        return [
            LogEntry(
                log_id="log-structural",
                level=LogLevel.WARNING,
                message="Reranking config appears ineffective",
                raw=(
                    "structural_hint: which function reads RERANKING_MODEL_NAME "
                    "and which request path calls rerank_documents_with_scores()?"
                ),
                service_name="conversational_rag",
            )
        ]


class BehaviorMismatchLogProvider:
    """Return runtime evidence without a stack trace or exception."""

    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        return [
            LogEntry(
                log_id="log-behavior",
                level=LogLevel.INFO,
                message="Request completed with unexpected result quality",
                raw="request completed status=200 selected_strategy=fast_path",
                service_name="generic_service",
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
                context_id="src/rag/router.py:route_query",
                file_path="src/rag/router.py",
                function_name="route_query",
                line_start=40,
                line_end=45,
                snippet="def route_query(...): return response['output']",
                relevance_score=0.91,
            )
        ]


class FakeCodeGraphProvider:
    """Return one structural graph context item for graph investigator tests."""

    async def search_graph(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeGraphContext]:
        return [
            CodeGraphContext(
                context_id="src/rag/router.py:route_query",
                file_path="src/rag/router.py",
                relative_path="src/rag/router.py",
                symbol_name="route_query",
                symbol_type="function",
                qualified_symbol="route_query",
                line_start=40,
                line_end=45,
                calls=["parse_router_response"],
                called_by=["answer_question"],
                content=(
                    "src/rag/router.py:route_query is called by answer_question "
                    "and calls parse_router_response."
                ),
                relevance_score=0.9,
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


class FakeKnowledgeBaseProvider:
    """Return one knowledge-base item that explains expected routing behavior."""

    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        return [
            KnowledgeContext(
                context_id="kb-1",
                document_name="query-routing-expectations.md",
                section_title="Query Routing Expectations",
                content="Summary-style queries should use document-level retrieval.",
                relevance_score=0.88,
            )
        ]


class FakeHistoricalRCAProvider:
    """Return one similar prior RCA context."""

    async def search_history(
        self,
        queries: list[str],
        *,
        current_incident_id: str | None = None,
        limit: int = 5,
    ) -> list[HistoricalRCAContext]:
        return [
            HistoricalRCAContext(
                context_id="historical-INC-OLD",
                incident_id="INC-OLD",
                title="Prior duplicate record incident",
                root_cause="Prior RCA found duplicate handling used unstable identity.",
                confidence_score=0.82,
                content="Similar prior incident involved duplicate records.",
                relevance_score=0.77,
            )
        ]


class FakePatchContextProvider:
    """Return exact source text for patch generation tests."""

    async def read_file(self, file_path: str) -> str | None:
        if file_path == "src/rag/router.py":
            return "def route_query():\n    return response['output']\n"
        return None


class FakePatchLLMClient:
    """Return a stable human-reviewable diff suggestion."""

    async def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return "unused"

    async def generate_structured(self, prompt, output_schema, *, system_prompt=None):
        return PatchGenerationResult(
            file_patches=[
                FilePatch(
                    file_path="src/rag/router.py",
                    unified_diff=(
                        "--- a/src/rag/router.py\n"
                        "+++ b/src/rag/router.py\n"
                        "@@\n"
                        "-    return response['output']\n"
                        "+    return response.get('output')\n"
                    ),
                    reason="Guard the missing output key.",
                    evidence_ids=["evidence-src/rag/router.py:route_query"],
                    confidence_score=0.7,
                )
            ]
        )


class FakeReportStore:
    """Pretend to persist generated reports and return a stable path."""

    async def save_report(
        self,
        report: RCAReport,
        *,
        solution: SolutionRecommendation | None = None,
        patch_suggestion: PatchSuggestion | None = None,
    ) -> list[Path]:
        paths = [Path(f"reports/incidents/{report.incident_id}/rca.md")]
        if solution is not None:
            paths.append(Path(f"reports/incidents/{report.incident_id}/solution.md"))
        if patch_suggestion is not None:
            paths.append(Path(f"reports/incidents/{report.incident_id}/patch.md"))
        return paths

    async def get_report(self, incident_id: str) -> RCAReport | None:
        return None


class RetryRequiredEvaluator:
    """Force a retry-required evaluation even when replans are exhausted."""

    async def run(self, state: WorkflowState) -> EvidenceEvaluationResult:
        return EvidenceEvaluationResult(
            evaluation_id="eval-retry",
            incident_id=state.incident.incident_id,
            can_write_rca=False,
            confidence_score=0.2,
            reason="Evidence is incomplete and retry is required.",
            retry_required=True,
            missing_evidence=["Implementation code evidence is missing."],
        )


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
    *,
    incident_provider=None,
    evidence_evaluator_agent=None,
    log_provider=None,
    knowledge_base_provider=None,
    historical_rca_provider=None,
    max_steps: int = 12,
    max_replans: int = 2,
    include_patch_plan: bool = False,
    include_patch_diff: bool = False,
) -> DynamicBugResolutionGraphWorkflow:
    """Create the graph workflow with deterministic local test doubles."""
    return DynamicBugResolutionGraphWorkflow(
        incident_provider=incident_provider or FakeIncidentProvider(),
        supervisor_agent=supervisor,  # type: ignore[arg-type]
        guardrail_engine=GuardrailEngine(),
        log_investigator_agent=LogInvestigatorAgent(log_provider or FakeLogProvider()),
        code_investigator_agent=CodeInvestigatorAgent(FakeCodeContextProvider()),
        code_graph_investigator_agent=CodeGraphInvestigatorAgent(FakeCodeGraphProvider()),
        historical_rca_investigator_agent=HistoricalRCAInvestigatorAgent(
            historical_rca_provider or FakeHistoricalRCAProvider()
        ),
        knowledge_base_investigator_agent=KnowledgeBaseInvestigatorAgent(
            knowledge_base_provider or EmptyKnowledgeBaseProvider()
        ),
        evidence_evaluator_agent=evidence_evaluator_agent or EvidenceEvaluatorAgent(),
        rca_writer_agent=RCAWriterAgent(),
        solution_recommendation_agent=SolutionRecommendationAgent(),
        patch_suggestion_agent=PatchSuggestionAgent(),
        patch_generator_agent=PatchGeneratorAgent(
            llm_client=FakePatchLLMClient(),
            patch_context_provider=FakePatchContextProvider(),
        ),
        report_writer_agent=ReportWriterAgent(FakeReportStore()),
        max_steps=max_steps,
        max_replans=max_replans,
        minimum_evidence_count_before_rca=2,
        include_patch_plan=include_patch_plan,
        include_patch_diff=include_patch_diff,
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
    assert state.report_artifact_paths == [
        Path("reports/incidents/INC-001/rca.md"),
        Path("reports/incidents/INC-001/solution.md"),
    ]
    assert step_agents[-3:] == [
        AgentName.RCA_WRITER,
        AgentName.SOLUTION_RECOMMENDER,
        AgentName.REPORT_WRITER,
    ]
    assert supervisor.call_count == 2


@pytest.mark.asyncio
async def test_graph_workflow_falls_back_to_logs_when_rca_is_chosen_before_evidence() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.RCA_WRITER, ["write RCA"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
        ]
    )
    workflow = make_graph_workflow(supervisor)

    state = await workflow.run("INC-001")

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert state.trace.guardrail_decisions[0].allowed is False
    assert state.trace.guardrail_decisions[0].fallback_next_agent == AgentName.LOG_INVESTIGATOR
    assert "runtime_evidence_required_first" in state.trace.guardrail_decisions[0].violated_rules
    assert state.trace.steps[0].agent_name == AgentName.RCA_WRITER
    assert state.trace.steps[0].run_status == AgentRunStatus.BLOCKED
    assert state.trace.steps[1].agent_name == AgentName.LOG_INVESTIGATOR
    assert state.trace.steps[1].run_status == AgentRunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_graph_workflow_routes_to_graph_investigator() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
            decision("decision-3", AgentName.GRAPH_INVESTIGATOR, ["route_query callers"]),
        ]
    )
    workflow = make_graph_workflow(
        supervisor,
        log_provider=StructuralHintLogProvider(),
    )

    state = await workflow.run("INC-001")

    assert supervisor.call_count == 3
    assert any(step.agent_name == AgentName.GRAPH_INVESTIGATOR for step in state.trace.steps)
    assert any(
        evidence.source_type == EvidenceSourceType.GRAPH
        and evidence.metadata["qualified_symbol"] == "route_query"
        for evidence in state.evidence_items
    )
    assert state.investigation_status == InvestigationStatus.COMPLETED


@pytest.mark.asyncio
async def test_graph_workflow_falls_back_to_code_when_kb_is_chosen_without_code() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.KNOWLEDGE_BASE_INVESTIGATOR, ["router docs"]),
        ]
    )
    workflow = make_graph_workflow(supervisor)

    state = await workflow.run("INC-001")

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert any(
        "missing_code_evidence_should_route_to_code" in guardrail_decision.violated_rules
        and guardrail_decision.fallback_next_agent == AgentName.CODE_INVESTIGATOR
        for guardrail_decision in state.trace.guardrail_decisions
    )
    assert any(
        step.agent_name == AgentName.CODE_INVESTIGATOR
        and step.run_status == AgentRunStatus.SUCCEEDED
        for step in state.trace.steps
    )


@pytest.mark.asyncio
async def test_graph_workflow_blocks_repeated_kb_and_falls_back_to_code() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision(
                "decision-2",
                AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
                ["routing expectations"],
            ),
            decision(
                "decision-3",
                AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
                ["product expectations"],
            ),
        ]
    )
    workflow = make_graph_workflow(
        supervisor,
        knowledge_base_provider=FakeKnowledgeBaseProvider(),
    )

    state = await workflow.run("INC-001")

    kb_steps = [
        step
        for step in state.trace.steps
        if step.agent_name == AgentName.KNOWLEDGE_BASE_INVESTIGATOR
    ]

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert [step.run_status for step in kb_steps] == [
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.BLOCKED,
    ]
    assert any(
        "missing_code_evidence_should_route_to_code" in guardrail_decision.violated_rules
        and guardrail_decision.fallback_next_agent == AgentName.CODE_INVESTIGATOR
        for guardrail_decision in state.trace.guardrail_decisions
    )
    assert any(
        step.agent_name == AgentName.CODE_INVESTIGATOR
        and step.run_status == AgentRunStatus.SUCCEEDED
        for step in state.trace.steps
    )


@pytest.mark.asyncio
async def test_graph_workflow_routes_to_kb_for_expected_behavior_mismatch() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-BEHAVIOR logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["selected strategy code"]),
            decision(
                "decision-3",
                AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
                ["expected behavior deployment policy"],
            ),
        ]
    )
    workflow = make_graph_workflow(
        supervisor,
        incident_provider=BehaviorMismatchIncidentProvider(),
        log_provider=BehaviorMismatchLogProvider(),
        knowledge_base_provider=FakeKnowledgeBaseProvider(),
    )

    state = await workflow.run("INC-BEHAVIOR")

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert supervisor.call_count == 3
    assert any(
        step.agent_name == AgentName.KNOWLEDGE_BASE_INVESTIGATOR
        and step.run_status == AgentRunStatus.SUCCEEDED
        for step in state.trace.steps
    )
    assert any(
        seen_state.evidence_evaluation is not None
        and any(
            "Knowledge-base evidence is missing" in missing
            for missing in seen_state.evidence_evaluation.missing_evidence
        )
        for seen_state in supervisor.seen_states
    )


@pytest.mark.asyncio
async def test_graph_workflow_routes_to_historical_rca_for_recurrence_signal() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-REPEAT logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["duplicate handling code"]),
            decision(
                "decision-3",
                AgentName.HISTORICAL_RCA_INVESTIGATOR,
                ["similar previous duplicate record RCA"],
            ),
        ]
    )
    workflow = make_graph_workflow(
        supervisor,
        incident_provider=RecurringIncidentProvider(),
    )

    state = await workflow.run("INC-REPEAT")

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert supervisor.call_count == 3
    assert any(
        step.agent_name == AgentName.HISTORICAL_RCA_INVESTIGATOR
        and step.run_status == AgentRunStatus.SUCCEEDED
        for step in state.trace.steps
    )
    assert any(
        evidence.source_type == EvidenceSourceType.HISTORICAL_RCA
        for evidence in state.evidence_items
    )


@pytest.mark.asyncio
async def test_graph_workflow_finishes_low_confidence_when_retry_exhausts_replans() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
        ]
    )
    workflow = make_graph_workflow(
        supervisor,
        evidence_evaluator_agent=RetryRequiredEvaluator(),
        max_replans=0,
    )

    state = await workflow.run("INC-001")

    assert state.low_confidence is True
    assert state.investigation_status == InvestigationStatus.MAX_STEPS_REACHED
    assert state.replan_count == 0
    assert state.evidence_evaluation is not None
    assert state.evidence_evaluation.retry_required is True
    assert state.rca_report is None
    assert state.solution_recommendation is None
    assert state.final_report_path is None


@pytest.mark.asyncio
async def test_graph_workflow_routes_to_final_writers_when_evaluation_can_write_rca() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
        ]
    )
    workflow = make_graph_workflow(supervisor)

    state = await workflow.run("INC-001")

    step_agents = [step.agent_name for step in state.trace.steps]

    assert state.evidence_evaluation is not None
    assert state.evidence_evaluation.can_write_rca is True
    assert state.rca_report is not None
    assert state.solution_recommendation is not None
    assert state.final_report_path == Path("reports/incidents/INC-001/rca.md")
    assert step_agents[-3:] == [
        AgentName.RCA_WRITER,
        AgentName.SOLUTION_RECOMMENDER,
        AgentName.REPORT_WRITER,
    ]


@pytest.mark.asyncio
async def test_graph_workflow_can_generate_optional_patch_plan() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
        ]
    )
    workflow = make_graph_workflow(supervisor, include_patch_plan=True)

    state = await workflow.run("INC-001")
    step_agents = [step.agent_name for step in state.trace.steps]

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert state.patch_suggestion is not None
    assert state.patch_suggestion.human_approval_required is True
    assert state.patch_suggestion.analyze_only is True
    assert state.patch_suggestion.target_repo_modified is False
    assert state.report_artifact_paths == [
        Path("reports/incidents/INC-001/rca.md"),
        Path("reports/incidents/INC-001/solution.md"),
        Path("reports/incidents/INC-001/patch.md"),
    ]
    assert step_agents[-4:] == [
        AgentName.RCA_WRITER,
        AgentName.SOLUTION_RECOMMENDER,
        AgentName.PATCH_SUGGESTER,
        AgentName.REPORT_WRITER,
    ]


@pytest.mark.asyncio
async def test_graph_workflow_can_generate_optional_patch_diff() -> None:
    supervisor = FakeSupervisorAgent(
        [
            decision("decision-1", AgentName.LOG_INVESTIGATOR, ["INC-001 logs"]),
            decision("decision-2", AgentName.CODE_INVESTIGATOR, ["router.py TypeError"]),
        ]
    )
    workflow = make_graph_workflow(supervisor, include_patch_diff=True)

    state = await workflow.run("INC-001")
    step_agents = [step.agent_name for step in state.trace.steps]

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert state.patch_suggestion is not None
    assert state.patch_suggestion.file_patches
    assert state.patch_suggestion.file_patches[0].file_path == "src/rag/router.py"
    assert state.patch_suggestion.target_repo_modified is False
    assert step_agents[-5:] == [
        AgentName.RCA_WRITER,
        AgentName.SOLUTION_RECOMMENDER,
        AgentName.PATCH_SUGGESTER,
        AgentName.PATCH_GENERATOR,
        AgentName.REPORT_WRITER,
    ]
