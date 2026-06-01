"""LangGraph skeleton for the supervisor-led dynamic investigation workflow."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from pydantic import Field

from bug_resolver.agents import (
    CodeGraphInvestigatorAgent,
    CodeGraphInvestigatorInput,
    CodeInvestigatorAgent,
    CodeInvestigatorInput,
    EvidenceEvaluatorAgent,
    HistoricalRCAInvestigatorAgent,
    HistoricalRCAInvestigatorInput,
    KnowledgeBaseInvestigatorAgent,
    KnowledgeBaseInvestigatorInput,
    LogInvestigatorAgent,
    LogInvestigatorInput,
    PatchGeneratorAgent,
    PatchGeneratorInput,
    PatchSuggestionAgent,
    PatchSuggestionInput,
    RCAWriterAgent,
    ReportWriterAgent,
    ReportWriterInput,
    SolutionRecommendationAgent,
    SupervisorAgent,
)
from bug_resolver.errors import normalize_error
from bug_resolver.providers.incident import IncidentProvider
from bug_resolver.rules import GuardrailEngine
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    EvidenceItem,
    GuardrailDecision,
    InvestigationStatus,
    WorkflowState,
)
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.utils.ids import new_agent_decision_id
from bug_resolver.utils.observability import get_logger, traceable
from bug_resolver.workflows.workflow_execution_recorder import WorkflowExecutionRecorder


logger = get_logger(__name__)


GraphRoute = Literal[
    "supervisor",
    "guardrail",
    "log_investigator",
    "code_investigator",
    "graph_investigator",
    "historical_rca_investigator",
    "knowledge_base_investigator",
    "evidence_evaluator",
    "rca_writer",
    "solution_recommender",
    "patch_suggester",
    "patch_generator",
    "report_writer",
    "finish",
]


class DynamicGraphState(StrictBaseModel):
    """Internal LangGraph state envelope around the existing WorkflowState."""

    incident_id: str = Field(..., min_length=1)
    workflow_state: WorkflowState | None = None
    next_route: GraphRoute = "supervisor"


class DynamicBugResolutionGraphWorkflow:
    """
    LangGraph implementation of the dynamic bug-resolution workflow.

    This class intentionally mirrors DynamicBugResolutionWorkflow without
    replacing it. The CLI can continue using the manual workflow while this
    graph implementation matures behind the same agent and schema contracts.
    """

    def __init__(
        self,
        *,
        incident_provider: IncidentProvider,
        supervisor_agent: SupervisorAgent,
        guardrail_engine: GuardrailEngine,
        log_investigator_agent: LogInvestigatorAgent,
        code_investigator_agent: CodeInvestigatorAgent,
        knowledge_base_investigator_agent: KnowledgeBaseInvestigatorAgent,
        evidence_evaluator_agent: EvidenceEvaluatorAgent,
        rca_writer_agent: RCAWriterAgent,
        solution_recommendation_agent: SolutionRecommendationAgent,
        report_writer_agent: ReportWriterAgent,
        patch_suggestion_agent: PatchSuggestionAgent | None = None,
        patch_generator_agent: PatchGeneratorAgent | None = None,
        code_graph_investigator_agent: CodeGraphInvestigatorAgent | None = None,
        historical_rca_investigator_agent: HistoricalRCAInvestigatorAgent | None = None,
        max_steps: int = 12,
        max_replans: int = 2,
        max_agent_invocations_per_agent: int = 3,
        confidence_threshold: float = 0.75,
        minimum_evidence_count_before_rca: int = 2,
        include_patch_plan: bool = False,
        include_patch_diff: bool = False,
    ) -> None:
        self._incident_provider = incident_provider
        self._supervisor_agent = supervisor_agent
        self._guardrail_engine = guardrail_engine
        self._log_investigator_agent = log_investigator_agent
        self._code_investigator_agent = code_investigator_agent
        self._code_graph_investigator_agent = code_graph_investigator_agent
        self._historical_rca_investigator_agent = historical_rca_investigator_agent
        self._knowledge_base_investigator_agent = knowledge_base_investigator_agent
        self._evidence_evaluator_agent = evidence_evaluator_agent
        self._rca_writer_agent = rca_writer_agent
        self._solution_recommendation_agent = solution_recommendation_agent
        self._patch_suggestion_agent = patch_suggestion_agent
        self._patch_generator_agent = patch_generator_agent
        self._report_writer_agent = report_writer_agent
        self._max_steps = max_steps
        self._max_replans = max_replans
        self._max_agent_invocations_per_agent = max_agent_invocations_per_agent
        self._confidence_threshold = confidence_threshold
        self._minimum_evidence_count_before_rca = minimum_evidence_count_before_rca
        self._include_patch_plan = include_patch_plan or include_patch_diff
        self._include_patch_diff = include_patch_diff
        self._execution_recorder = WorkflowExecutionRecorder()
        self._graph = self._build_graph().compile()

    @traceable(name="workflow.graph.run", run_type="chain")
    async def run(self, incident_id: str) -> WorkflowState:
        """Run a LangGraph-backed investigation and return the final WorkflowState."""
        logger.info("graph workflow started incident_id=%s", incident_id)
        graph_input = DynamicGraphState(incident_id=incident_id)
        graph_output = await self._graph.ainvoke(graph_input)
        final_graph_state = DynamicGraphState.model_validate(graph_output)

        if final_graph_state.workflow_state is None:
            raise ValueError("LangGraph workflow finished without a WorkflowState")

        state = final_graph_state.workflow_state
        logger.info(
            "graph workflow finished incident_id=%s status=%s evidence_count=%s steps=%s",
            incident_id,
            state.investigation_status.value,
            len(state.evidence_items),
            len(state.trace.steps),
        )
        return state

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(DynamicGraphState)

        graph.add_node("initialize_state", self._initialize_state)
        graph.add_node("supervisor", self._supervisor)
        graph.add_node("guardrail", self._guardrail)
        graph.add_node("log_investigator", self._log_investigator)
        graph.add_node("code_investigator", self._code_investigator)
        graph.add_node("graph_investigator", self._graph_investigator)
        graph.add_node("historical_rca_investigator", self._historical_rca_investigator)
        graph.add_node("knowledge_base_investigator", self._knowledge_base_investigator)
        graph.add_node("evidence_evaluator", self._evidence_evaluator)
        graph.add_node("rca_writer", self._rca_writer)
        graph.add_node("solution_recommender", self._solution_recommender)
        graph.add_node("patch_suggester", self._patch_suggester)
        graph.add_node("patch_generator", self._patch_generator)
        graph.add_node("report_writer", self._report_writer)
        graph.add_node("finish", self._finish)

        graph.add_edge(START, "initialize_state")
        graph.add_edge("initialize_state", "supervisor")
        graph.add_edge("supervisor", "guardrail")
        graph.add_conditional_edges(
            "guardrail",
            self._route_after_guardrail,
            {
                "log_investigator": "log_investigator",
                "code_investigator": "code_investigator",
                "graph_investigator": "graph_investigator",
                "historical_rca_investigator": "historical_rca_investigator",
                "knowledge_base_investigator": "knowledge_base_investigator",
                "evidence_evaluator": "evidence_evaluator",
                "rca_writer": "rca_writer",
                "solution_recommender": "solution_recommender",
                "patch_suggester": "patch_suggester",
                "patch_generator": "patch_generator",
                "report_writer": "report_writer",
                "finish": "finish",
            },
        )
        graph.add_edge("log_investigator", "evidence_evaluator")
        graph.add_edge("code_investigator", "evidence_evaluator")
        graph.add_edge("graph_investigator", "evidence_evaluator")
        graph.add_edge("historical_rca_investigator", "evidence_evaluator")
        graph.add_edge("knowledge_base_investigator", "evidence_evaluator")
        graph.add_conditional_edges(
            "evidence_evaluator",
            self._route_after_evidence_evaluation,
            {
                "supervisor": "supervisor",
                "rca_writer": "rca_writer",
                "finish": "finish",
            },
        )
        graph.add_conditional_edges(
            "rca_writer",
            self._route_after_rca_writer,
            {
                "solution_recommender": "solution_recommender",
                "finish": "finish",
            },
        )
        graph.add_conditional_edges(
            "solution_recommender",
            self._route_after_solution_recommendation,
            {
                "patch_suggester": "patch_suggester",
                "report_writer": "report_writer",
                "finish": "finish",
            },
        )
        graph.add_conditional_edges(
            "patch_suggester",
            self._route_after_patch_suggestion,
            {
                "patch_generator": "patch_generator",
                "report_writer": "report_writer",
            },
        )
        graph.add_conditional_edges(
            "patch_generator",
            self._route_after_patch_generation,
            {
                "report_writer": "report_writer",
                "finish": "finish",
            },
        )
        graph.add_edge("report_writer", "finish")
        graph.add_edge("finish", END)

        return graph

    async def _initialize_state(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        incident = await self._incident_provider.get_incident(graph_state.incident_id)
        graph_state.workflow_state = WorkflowState(
            incident=incident,
            investigation_status=InvestigationStatus.RUNNING,
            max_steps=self._max_steps,
            max_replans=self._max_replans,
            max_agent_invocations_per_agent=self._max_agent_invocations_per_agent,
            confidence_threshold=self._confidence_threshold,
            minimum_evidence_count_before_rca=self._minimum_evidence_count_before_rca,
        )
        graph_state.next_route = "supervisor"
        return graph_state

    async def _supervisor(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        if not state.can_take_step():
            state.mark_low_confidence()
            state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
            graph_state.next_route = "finish"
            return graph_state

        decision = await self._supervisor_agent.run(state)
        state.record_decision(decision)
        logger.info(
            "graph workflow decision incident_id=%s decision_id=%s next_agent=%s route=guardrail",
            state.incident.incident_id,
            decision.decision_id,
            decision.next_agent.value,
        )
        graph_state.next_route = "guardrail"
        return graph_state

    async def _guardrail(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._current_decision(state)

        guardrail_decision = self._guardrail_engine.validate_decision(
            state=state,
            decision=decision,
        )
        state.record_guardrail_decision(guardrail_decision)

        if guardrail_decision.allowed:
            graph_state.next_route = self._route_for_agent(decision.next_agent)
            return graph_state

        self._record_blocked_guardrail_step(
            state=state,
            decision=decision,
            guardrail_decision=guardrail_decision,
        )
        if not state.can_take_step():
            state.mark_low_confidence()
            state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
            graph_state.next_route = "finish"
            return graph_state

        fallback_agent = guardrail_decision.fallback_next_agent
        if fallback_agent is None:
            state.add_error(guardrail_decision.reason)
            graph_state.next_route = "finish"
            return graph_state

        if fallback_agent == AgentName.FINISH:
            state.mark_low_confidence()
            graph_state.next_route = "finish"
            return graph_state

        fallback_decision = AgentDecision(
            decision_id=new_agent_decision_id(),
            next_agent=fallback_agent,
            reason=f"Guardrail fallback after blocked decision: {guardrail_decision.reason}",
            queries=decision.queries,
            expected_evidence=decision.expected_evidence,
            should_continue=True,
            metadata={"fallback_for": decision.decision_id},
        )
        state.record_decision(fallback_decision)
        graph_state.next_route = self._route_for_agent(fallback_agent)
        return graph_state

    async def _log_investigator(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._current_decision(state)
        try:
            evidence_items = await self._log_investigator_agent.run(
                LogInvestigatorInput(
                    incident_id=state.incident.incident_id,
                    decision=decision,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            graph_state.next_route = "evidence_evaluator"
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
        return graph_state

    async def _code_investigator(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._current_decision(state)
        try:
            evidence_items = await self._code_investigator_agent.run(
                CodeInvestigatorInput(
                    decision=decision,
                    incident=state.incident,
                    evidence_items=state.evidence_items,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            graph_state.next_route = "evidence_evaluator"
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
        return graph_state

    async def _graph_investigator(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._current_decision(state)
        if self._code_graph_investigator_agent is None:
            self._record_blocked_unsupported_agent(state, decision)
            graph_state.next_route = "evidence_evaluator"
            return graph_state

        try:
            evidence_items = await self._code_graph_investigator_agent.run(
                CodeGraphInvestigatorInput(
                    decision=decision,
                    evidence_items=state.evidence_items,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            graph_state.next_route = "evidence_evaluator"
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
        return graph_state

    async def _historical_rca_investigator(
        self,
        graph_state: DynamicGraphState,
    ) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._current_decision(state)
        if self._historical_rca_investigator_agent is None:
            self._record_blocked_unsupported_agent(state, decision)
            graph_state.next_route = "evidence_evaluator"
            return graph_state

        try:
            evidence_items = await self._historical_rca_investigator_agent.run(
                HistoricalRCAInvestigatorInput(
                    incident_id=state.incident.incident_id,
                    decision=decision,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            graph_state.next_route = "evidence_evaluator"
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
        return graph_state

    async def _knowledge_base_investigator(
        self,
        graph_state: DynamicGraphState,
    ) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._current_decision(state)
        try:
            evidence_items = await self._knowledge_base_investigator_agent.run(
                KnowledgeBaseInvestigatorInput(
                    decision=decision,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            graph_state.next_route = "evidence_evaluator"
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
        return graph_state

    async def _evidence_evaluator(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._ensure_evidence_evaluator_decision(state)

        guardrail_decision = self._guardrail_engine.validate_decision(
            state=state,
            decision=decision,
        )
        state.record_guardrail_decision(guardrail_decision)

        if not guardrail_decision.allowed:
            if state.can_take_step():
                self._record_blocked_guardrail_step(
                    state=state,
                    decision=decision,
                    guardrail_decision=guardrail_decision,
                )
            state.mark_low_confidence()
            state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
            graph_state.next_route = "finish"
            return graph_state

        try:
            evaluation = await self._evidence_evaluator_agent.run(state)
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
            return graph_state
        state.evidence_evaluation = evaluation
        if evaluation.retry_required:
            if state.can_replan():
                state.increment_replan()
            elif not self._can_retry_for_required_evidence(state):
                state.mark_low_confidence()
                state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
                graph_state.next_route = "finish"
                return graph_state
        self._record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=[],
            output_summary=evaluation.reason,
        )
        graph_state.next_route = self._route_after_evidence_evaluation(graph_state)
        return graph_state

    async def _rca_writer(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        decision = self._ensure_forced_decision(
            state=state,
            agent_name=AgentName.RCA_WRITER,
            reason="Evidence evaluation says RCA can be written.",
        )
        try:
            state.rca_report = await self._rca_writer_agent.run(state)
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
            return graph_state
        self._record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=state.rca_report.evidence_ids,
            output_summary=f"Generated RCA report {state.rca_report.report_id}.",
        )
        graph_state.next_route = "solution_recommender"
        return graph_state

    async def _solution_recommender(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        if state.rca_report is None:
            raise ValueError("solution recommendation requires RCA report")
        decision = self._ensure_forced_decision(
            state=state,
            agent_name=AgentName.SOLUTION_RECOMMENDER,
            reason="RCA report is ready; generate solution recommendation.",
        )
        try:
            state.solution_recommendation = await self._solution_recommendation_agent.run(
                state.rca_report
            )
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
            return graph_state
        self._record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=state.solution_recommendation.evidence_ids,
            output_summary=state.solution_recommendation.summary,
        )
        graph_state.next_route = self._route_after_solution_recommendation(graph_state)
        return graph_state

    async def _patch_suggester(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        if not self._include_patch_plan:
            graph_state.next_route = "report_writer"
            return graph_state
        if state.rca_report is None:
            raise ValueError("patch suggestion requires RCA report")
        if state.solution_recommendation is None:
            raise ValueError("patch suggestion requires solution recommendation")
        decision = self._ensure_forced_decision(
            state=state,
            agent_name=AgentName.PATCH_SUGGESTER,
            reason="Optional patch suggestion requested; generate analyze-only patch plan.",
        )
        if self._patch_suggestion_agent is None:
            self._record_blocked_unsupported_agent(state, decision)
            graph_state.next_route = "report_writer"
            return graph_state

        try:
            state.patch_suggestion = await self._patch_suggestion_agent.run(
                PatchSuggestionInput(
                    rca_report=state.rca_report,
                    solution_recommendation=state.solution_recommendation,
                    evidence_items=state.evidence_items,
                )
            )
        except Exception as exc:
            self._handle_node_error(
                graph_state,
                state,
                decision,
                exc,
                recoverable_route="report_writer",
            )
            return graph_state
        self._record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=state.patch_suggestion.evidence_ids,
            output_summary=state.patch_suggestion.summary,
        )
        graph_state.next_route = "report_writer"
        return graph_state

    async def _patch_generator(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        if not self._include_patch_diff:
            graph_state.next_route = "report_writer"
            return graph_state
        if state.rca_report is None:
            raise ValueError("patch generation requires RCA report")
        if state.solution_recommendation is None:
            raise ValueError("patch generation requires solution recommendation")
        if state.patch_suggestion is None:
            raise ValueError("patch generation requires patch suggestion")
        decision = self._ensure_forced_decision(
            state=state,
            agent_name=AgentName.PATCH_GENERATOR,
            reason="Optional patch diff requested; generate analyze-only unified diffs.",
        )
        if self._patch_generator_agent is None:
            self._record_blocked_unsupported_agent(state, decision)
            graph_state.next_route = "report_writer"
            return graph_state

        try:
            generation_result = await self._patch_generator_agent.run(
                PatchGeneratorInput(
                    rca_report=state.rca_report,
                    solution_recommendation=state.solution_recommendation,
                    affected_files=state.patch_suggestion.affected_files,
                    evidence_ids=state.patch_suggestion.evidence_ids,
                    evidence_items=state.evidence_items,
                )
            )
        except Exception as exc:
            self._handle_node_error(
                graph_state,
                state,
                decision,
                exc,
                recoverable_route="report_writer",
            )
            return graph_state
        state.patch_suggestion = state.patch_suggestion.model_copy(
            update={
                "file_patches": generation_result.file_patches,
                "test_patches": generation_result.test_patches,
                "open_questions": self._merge_strings(
                    state.patch_suggestion.open_questions,
                    generation_result.open_questions,
                ),
                "warnings": self._merge_strings(
                    state.patch_suggestion.warnings,
                    generation_result.warnings,
                ),
            }
        )
        self._record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=state.patch_suggestion.evidence_ids,
            output_summary=(
                "Generated patch diffs."
                if generation_result.generated_diff
                else "Patch diff generation skipped."
            ),
        )
        graph_state.next_route = "report_writer"
        return graph_state

    async def _report_writer(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        state = self._state(graph_state)
        if state.rca_report is None:
            raise ValueError("report writing requires RCA report")
        decision = self._ensure_forced_decision(
            state=state,
            agent_name=AgentName.REPORT_WRITER,
            reason="RCA and solution are ready; save final report.",
            should_continue=False,
        )
        try:
            written_paths = await self._report_writer_agent.run(
                ReportWriterInput(
                    report=state.rca_report,
                    solution=state.solution_recommendation,
                    patch_suggestion=state.patch_suggestion,
                )
            )
        except Exception as exc:
            self._handle_node_error(graph_state, state, decision, exc)
            return graph_state
        state.final_report_path = written_paths[0]
        state.report_artifact_paths = written_paths
        state.investigation_status = InvestigationStatus.COMPLETED
        self._record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=state.rca_report.evidence_ids,
            output_summary=f"Saved report to {written_paths[0]}.",
        )
        graph_state.next_route = "finish"
        return graph_state

    async def _finish(self, graph_state: DynamicGraphState) -> DynamicGraphState:
        return graph_state

    def _route_after_guardrail(self, graph_state: DynamicGraphState) -> GraphRoute:
        return graph_state.next_route

    def _route_after_evidence_evaluation(self, graph_state: DynamicGraphState) -> GraphRoute:
        state = self._state(graph_state)
        if state.investigation_status in {
            InvestigationStatus.FAILED,
            InvestigationStatus.MAX_STEPS_REACHED,
        } or state.low_confidence:
            return "finish"

        evaluation = state.evidence_evaluation

        if evaluation is not None and evaluation.can_write_rca:
            if not self._has_capacity_for_finalization(state):
                state.mark_low_confidence()
                state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
                return "finish"
            return "rca_writer"

        if state.can_take_step() and evaluation is not None and evaluation.retry_required:
            return "supervisor"

        state.mark_low_confidence()
        state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
        return "finish"

    def _has_capacity_for_finalization(self, state: WorkflowState) -> bool:
        required_steps = 3
        if self._include_patch_plan:
            required_steps += 1
        if self._include_patch_diff:
            required_steps += 1
        return len(state.trace.steps) + required_steps <= state.max_steps

    def _route_after_rca_writer(self, graph_state: DynamicGraphState) -> GraphRoute:
        state = self._state(graph_state)
        if state.investigation_status == InvestigationStatus.FAILED:
            return "finish"
        return "solution_recommender"

    def _route_after_solution_recommendation(
        self,
        graph_state: DynamicGraphState,
    ) -> GraphRoute:
        state = self._state(graph_state)
        if state.investigation_status == InvestigationStatus.FAILED:
            return "finish"

        if (
            self._include_patch_plan
            and state.patch_suggestion is None
            and state.rca_report is not None
            and state.solution_recommendation is not None
        ):
            return "patch_suggester"

        return "report_writer"

    def _route_after_patch_suggestion(self, graph_state: DynamicGraphState) -> GraphRoute:
        state = self._state(graph_state)
        if state.investigation_status == InvestigationStatus.FAILED:
            return "finish"

        if (
            self._include_patch_diff
            and state.patch_suggestion is not None
            and not state.patch_suggestion.file_patches
            and not state.patch_suggestion.test_patches
        ):
            return "patch_generator"

        return "report_writer"

    def _route_after_patch_generation(self, graph_state: DynamicGraphState) -> GraphRoute:
        state = self._state(graph_state)
        if state.investigation_status == InvestigationStatus.FAILED:
            return "finish"
        return "report_writer"

    def _can_retry_for_structural_graph_evidence(self, state: WorkflowState) -> bool:
        evaluation = state.evidence_evaluation
        if evaluation is None:
            return False

        if "Structural graph evidence is missing." not in evaluation.missing_evidence:
            return False

        return (
            AgentName.GRAPH_INVESTIGATOR in state.allowed_agent_names
            and state.can_invoke_agent(AgentName.GRAPH_INVESTIGATOR)
        )

    def _can_retry_for_required_evidence(self, state: WorkflowState) -> bool:
        if self._can_retry_for_structural_graph_evidence(state):
            return True

        evaluation = state.evidence_evaluation
        if evaluation is None:
            return False

        if not any(
            "Knowledge-base evidence is missing" in missing_evidence
            for missing_evidence in evaluation.missing_evidence
        ):
            return False

        return (
            AgentName.KNOWLEDGE_BASE_INVESTIGATOR in state.allowed_agent_names
            and state.can_invoke_agent(AgentName.KNOWLEDGE_BASE_INVESTIGATOR)
        )

    def _ensure_evidence_evaluator_decision(self, state: WorkflowState) -> AgentDecision:
        current_decision = state.current_decision
        if current_decision and current_decision.next_agent == AgentName.EVIDENCE_EVALUATOR:
            return current_decision

        return self._ensure_forced_decision(
            state=state,
            agent_name=AgentName.EVIDENCE_EVALUATOR,
            reason="Evaluate evidence after latest investigation step.",
        )

    def _ensure_forced_decision(
        self,
        *,
        state: WorkflowState,
        agent_name: AgentName,
        reason: str,
        should_continue: bool = True,
    ) -> AgentDecision:
        current_decision = state.current_decision
        if (
            current_decision
            and current_decision.next_agent == agent_name
            and current_decision.metadata.get("forced_by_workflow") == "true"
        ):
            return current_decision

        decision = AgentDecision(
            decision_id=new_agent_decision_id(),
            next_agent=agent_name,
            reason=reason,
            queries=[],
            expected_evidence=[],
            should_continue=should_continue,
            metadata={"forced_by_workflow": "true"},
        )
        state.record_decision(decision)
        return decision

    def _record_successful_evidence_run(
        self,
        state: WorkflowState,
        decision: AgentDecision,
        evidence_items: list[EvidenceItem],
    ) -> None:
        self._execution_recorder.record_successful_evidence_run(
            state,
            decision,
            evidence_items,
        )

    def _record_successful_agent_run(
        self,
        *,
        state: WorkflowState,
        decision: AgentDecision,
        evidence_ids: list[str],
        output_summary: str,
    ) -> None:
        self._execution_recorder.record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=evidence_ids,
            output_summary=output_summary,
        )

    def _record_blocked_guardrail_step(
        self,
        *,
        state: WorkflowState,
        decision: AgentDecision,
        guardrail_decision: GuardrailDecision,
    ) -> None:
        self._execution_recorder.record_blocked_guardrail_step(
            state=state,
            decision=decision,
            guardrail_decision=guardrail_decision,
        )

    def _record_blocked_unsupported_agent(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> None:
        self._execution_recorder.record_blocked_unsupported_agent(state, decision)

    def _handle_node_error(
        self,
        graph_state: DynamicGraphState,
        state: WorkflowState,
        decision: AgentDecision,
        error: Exception,
        *,
        recoverable_route: GraphRoute = "evidence_evaluator",
    ) -> None:
        recoverable = self._is_recoverable_agent_failure(decision.next_agent)
        normalized_error = normalize_error(
            error,
            component=decision.next_agent.value,
            recoverable=recoverable,
            context={
                "incident_id": state.incident.incident_id,
                "decision_id": decision.decision_id,
                "agent": decision.next_agent.value,
            },
        )
        state.add_error(normalized_error)
        self._execution_recorder.record_failed_agent_run(
            state=state,
            decision=decision,
            error_message=normalized_error.user_message,
            recoverable=normalized_error.recoverable,
        )
        graph_state.next_route = recoverable_route if normalized_error.recoverable else "finish"

    def _is_recoverable_agent_failure(self, agent_name: AgentName) -> bool:
        return agent_name in {
            AgentName.LOG_INVESTIGATOR,
            AgentName.CODE_INVESTIGATOR,
            AgentName.GRAPH_INVESTIGATOR,
            AgentName.HISTORICAL_RCA_INVESTIGATOR,
            AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
            AgentName.PATCH_SUGGESTER,
            AgentName.PATCH_GENERATOR,
        }

    def _route_for_agent(self, agent_name: AgentName) -> GraphRoute:
        route_by_agent: dict[AgentName, GraphRoute] = {
            AgentName.LOG_INVESTIGATOR: "log_investigator",
            AgentName.CODE_INVESTIGATOR: "code_investigator",
            AgentName.GRAPH_INVESTIGATOR: "graph_investigator",
            AgentName.HISTORICAL_RCA_INVESTIGATOR: "historical_rca_investigator",
            AgentName.KNOWLEDGE_BASE_INVESTIGATOR: "knowledge_base_investigator",
            AgentName.EVIDENCE_EVALUATOR: "evidence_evaluator",
            AgentName.RCA_WRITER: "rca_writer",
            AgentName.SOLUTION_RECOMMENDER: "solution_recommender",
            AgentName.PATCH_SUGGESTER: "patch_suggester",
            AgentName.PATCH_GENERATOR: "patch_generator",
            AgentName.REPORT_WRITER: "report_writer",
            AgentName.FINISH: "finish",
        }
        route = route_by_agent.get(agent_name)
        if route is None:
            return "finish"
        return route

    def _state(self, graph_state: DynamicGraphState) -> WorkflowState:
        if graph_state.workflow_state is None:
            raise ValueError("LangGraph node requires initialized WorkflowState")
        return graph_state.workflow_state

    def _current_decision(self, state: WorkflowState) -> AgentDecision:
        if state.current_decision is None:
            raise ValueError("workflow state does not have a current decision")
        return state.current_decision

    def _merge_strings(self, *groups: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for value in group:
                normalized = value.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged

    def __repr__(self) -> str:
        return (
            "DynamicBugResolutionGraphWorkflow("
            f"max_steps={self._max_steps}, "
            f"max_replans={self._max_replans}, "
            f"confidence_threshold={self._confidence_threshold})"
        )
