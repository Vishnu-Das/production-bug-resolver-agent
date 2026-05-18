from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Literal, Protocol, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from bug_resolver.agents.code_context_agent import CodeContextAgent, CodeContextInput
from bug_resolver.agents.context_planning_agent import (
    ContextPlanningAgent,
    ContextPlanningInput,
)
from bug_resolver.agents.evidence_evaluator_agent import EvidenceEvaluatorAgent
from bug_resolver.agents.hypothesis_agent import HypothesisAgent, HypothesisInput
from bug_resolver.agents.incident_intake_agent import IncidentIntakeAgent
from bug_resolver.agents.knowledge_base_agent import KnowledgeBaseAgent, KnowledgeBaseInput
from bug_resolver.agents.log_analysis_agent import LogAnalysisAgent
from bug_resolver.agents.rca_agent import RCAAgent, RCAInput
from bug_resolver.agents.report_writer_agent import ReportWriterAgent, ReportWriterInput
from bug_resolver.agents.solution_recommendation_agent import SolutionRecommendationAgent
from bug_resolver.schemas.common import WorkflowStatus
from bug_resolver.schemas.incident_intake import IncidentIntakeRequest
from bug_resolver.schemas.logs import LogEntry
from bug_resolver.schemas.workflow_state import WorkflowState


class LogProvider(Protocol):
    """Minimal graph-facing log provider contract."""

    def get_logs(self, incident_id: str) -> list[LogEntry] | Awaitable[list[LogEntry]]:
        """Return logs for an incident."""


class GraphState(TypedDict):
    workflow_state: WorkflowState
    input_data: IncidentIntakeRequest
    retry_reason: str | None
    missing_evidence_hints: list[str]


class BugResolutionGraph:
    """
    LangGraph orchestration for the bug resolution workflow.

    This class keeps business behavior equivalent to BugResolutionWorkflow, but
    expresses the control flow as graph nodes and a conditional retry edge.
    """

    def __init__(
        self,
        *,
        incident_intake_agent: IncidentIntakeAgent,
        log_provider: LogProvider,
        log_analysis_agent: LogAnalysisAgent,
        context_planning_agent: ContextPlanningAgent,
        code_context_agent: CodeContextAgent,
        knowledge_base_agent: KnowledgeBaseAgent,
        hypothesis_agent: HypothesisAgent,
        rca_agent: RCAAgent,
        evidence_evaluator_agent: EvidenceEvaluatorAgent,
        solution_recommendation_agent: SolutionRecommendationAgent,
        report_writer_agent: ReportWriterAgent,
        max_retries: int = 2,
        confidence_threshold: float = 0.75,
        code_context_limit: int = 5,
        knowledge_context_limit: int = 5,
    ) -> None:
        self._incident_intake_agent = incident_intake_agent
        self._log_provider = log_provider
        self._log_analysis_agent = log_analysis_agent
        self._context_planning_agent = context_planning_agent
        self._code_context_agent = code_context_agent
        self._knowledge_base_agent = knowledge_base_agent
        self._hypothesis_agent = hypothesis_agent
        self._rca_agent = rca_agent
        self._evidence_evaluator_agent = evidence_evaluator_agent
        self._solution_recommendation_agent = solution_recommendation_agent
        self._report_writer_agent = report_writer_agent
        self._max_retries = max_retries
        self._confidence_threshold = confidence_threshold
        self._code_context_limit = code_context_limit
        self._knowledge_context_limit = knowledge_context_limit
        self._compiled_graph = self._build_graph().compile()

    async def run(self, input_data: IncidentIntakeRequest) -> WorkflowState:
        incident = await self._incident_intake_agent.run(input_data)

        initial_state = GraphState(
            workflow_state=WorkflowState(
                incident=incident,
                max_retries=self._max_retries,
                confidence_threshold=self._confidence_threshold,
            ),
            input_data=input_data,
            retry_reason=None,
            missing_evidence_hints=[],
        )

        try:
            result = await self._compiled_graph.ainvoke(initial_state)
            return result["workflow_state"]
        except Exception as exc:
            state = initial_state["workflow_state"]
            state.add_error(str(exc))
            return state

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(GraphState)

        graph.add_node("load_logs", self._load_logs)
        graph.add_node("analyze_logs", self._analyze_logs)
        graph.add_node("plan_context", self._plan_context)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("generate_hypotheses", self._generate_hypotheses)
        graph.add_node("generate_rca", self._generate_rca)
        graph.add_node("evaluate_evidence", self._evaluate_evidence)
        graph.add_node("recommend_solution", self._recommend_solution)
        graph.add_node("write_report", self._write_report)

        graph.add_edge(START, "load_logs")
        graph.add_edge("load_logs", "analyze_logs")
        graph.add_edge("analyze_logs", "plan_context")
        graph.add_edge("plan_context", "retrieve_context")
        graph.add_edge("retrieve_context", "generate_hypotheses")
        graph.add_edge("generate_hypotheses", "generate_rca")
        graph.add_edge("generate_rca", "evaluate_evidence")
        graph.add_conditional_edges(
            "evaluate_evidence",
            self._route_after_evidence_evaluation,
            {
                "retry": "plan_context",
                "continue": "recommend_solution",
            },
        )
        graph.add_edge("recommend_solution", "write_report")
        graph.add_edge("write_report", END)

        return graph

    async def _load_logs(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.incident is None:
            raise ValueError("graph cannot load logs without incident")

        logs = await self._get_logs(workflow_state.incident.incident_id)
        workflow_state.parsed_logs = logs
        workflow_state.raw_logs = [log.raw or log.message for log in logs]
        return state

    async def _analyze_logs(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        workflow_state.log_analysis = await self._log_analysis_agent.run(
            workflow_state.parsed_logs
        )
        workflow_state.status = WorkflowStatus.LOGS_ANALYZED
        return state

    async def _plan_context(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.incident is None:
            raise ValueError("graph cannot plan context without incident")
        if workflow_state.log_analysis is None:
            raise ValueError("graph cannot plan context without log analysis")

        workflow_state.context_plan = await self._context_planning_agent.run(
            ContextPlanningInput(
                incident=workflow_state.incident,
                log_analysis=workflow_state.log_analysis,
                retry_reason=state["retry_reason"],
                previous_missing_evidence_hints=state["missing_evidence_hints"],
            )
        )
        workflow_state.status = WorkflowStatus.CONTEXT_PLANNED
        return state

    async def _retrieve_context(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.context_plan is None:
            raise ValueError("graph cannot retrieve context without context plan")

        workflow_state.code_context = await self._code_context_agent.run(
            CodeContextInput(
                context_plan=workflow_state.context_plan,
                limit=self._code_context_limit,
            )
        )
        workflow_state.knowledge_context = await self._knowledge_base_agent.run(
            KnowledgeBaseInput(
                context_plan=workflow_state.context_plan,
                limit=self._knowledge_context_limit,
            )
        )
        workflow_state.status = WorkflowStatus.CONTEXT_RETRIEVED
        return state

    async def _generate_hypotheses(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.incident is None:
            raise ValueError("graph cannot generate hypotheses without incident")
        if workflow_state.log_analysis is None:
            raise ValueError("graph cannot generate hypotheses without log analysis")

        workflow_state.hypotheses = await self._hypothesis_agent.run(
            HypothesisInput(
                incident=workflow_state.incident,
                log_analysis=workflow_state.log_analysis,
                code_contexts=workflow_state.code_context,
                knowledge_contexts=workflow_state.knowledge_context,
            )
        )
        workflow_state.status = WorkflowStatus.HYPOTHESES_GENERATED
        return state

    async def _generate_rca(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.incident is None:
            raise ValueError("graph cannot generate RCA without incident")
        if workflow_state.log_analysis is None:
            raise ValueError("graph cannot generate RCA without log analysis")

        workflow_state.rca_report = await self._rca_agent.run(
            RCAInput(
                incident=workflow_state.incident,
                log_analysis=workflow_state.log_analysis,
                hypotheses=workflow_state.hypotheses,
                code_contexts=workflow_state.code_context,
                knowledge_contexts=workflow_state.knowledge_context,
            )
        )
        workflow_state.status = WorkflowStatus.RCA_GENERATED
        return state

    async def _evaluate_evidence(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.rca_report is None:
            raise ValueError("graph cannot evaluate evidence without RCA report")

        workflow_state.evidence_evaluation = await self._evidence_evaluator_agent.run(
            workflow_state.rca_report
        )

        should_retry = (
            workflow_state.evidence_evaluation.retry_required
            and workflow_state.evidence_evaluation.confidence_score
            < workflow_state.confidence_threshold
            and workflow_state.can_retry()
        )

        if should_retry:
            workflow_state.increment_retry()
            state["retry_reason"] = workflow_state.evidence_evaluation.reason
            state["missing_evidence_hints"] = [
                *workflow_state.evidence_evaluation.missing_evidence,
                *workflow_state.evidence_evaluation.improved_code_queries,
                *workflow_state.evidence_evaluation.improved_knowledge_queries,
            ]
        else:
            state["retry_reason"] = None
            state["missing_evidence_hints"] = []

        return state

    def _route_after_evidence_evaluation(
        self,
        state: GraphState,
    ) -> Literal["retry", "continue"]:
        if state["retry_reason"] is not None:
            return "retry"

        return "continue"

    async def _recommend_solution(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.rca_report is None:
            raise ValueError("graph cannot recommend solution without RCA report")

        workflow_state.solution_recommendation = (
            await self._solution_recommendation_agent.run(workflow_state.rca_report)
        )
        workflow_state.status = WorkflowStatus.SOLUTION_RECOMMENDED
        return state

    async def _write_report(self, state: GraphState) -> GraphState:
        workflow_state = state["workflow_state"]
        if workflow_state.rca_report is None:
            raise ValueError("graph cannot write report without RCA report")

        written_paths = await self._report_writer_agent.run(
            ReportWriterInput(
                report=workflow_state.rca_report,
                solution=workflow_state.solution_recommendation,
            )
        )
        workflow_state.final_report_path = written_paths[0]
        workflow_state.status = WorkflowStatus.REPORT_SAVED
        return state

    async def _get_logs(self, incident_id: str) -> list[LogEntry]:
        result = self._log_provider.get_logs(incident_id)
        if inspect.isawaitable(result):
            return await cast(Awaitable[list[LogEntry]], result)
        return result