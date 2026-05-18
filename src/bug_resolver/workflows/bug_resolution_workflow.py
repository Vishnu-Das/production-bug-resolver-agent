from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Protocol, cast

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
    """Minimal workflow-facing log provider contract."""

    def get_logs(self, incident_id: str) -> list[LogEntry] | Awaitable[list[LogEntry]]:
        """Return logs for an incident."""


class BugResolutionWorkflow:
    """
    Orchestrates the full bug investigation flow.

    This class is intentionally deterministic and class-based first.
    Later, the same steps can be moved into LangGraph nodes with conditional edges.
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

    async def run(self, input_data: IncidentIntakeRequest) -> WorkflowState:
        """
        Run one complete RCA investigation.

        The workflow always:
        - creates a structured incident
        - loads and analyzes logs
        - retrieves code and knowledge context
        - generates hypotheses and RCA
        - evaluates evidence
        - retries context retrieval if evidence is weak
        - recommends a solution
        - saves the report
        """
        incident = await self._incident_intake_agent.run(input_data)

        state = WorkflowState(
            incident=incident,
            max_retries=self._max_retries,
            confidence_threshold=self._confidence_threshold,
        )

        try:
            state.parsed_logs = await self._get_logs(incident.incident_id)
            state.raw_logs = [log.raw or log.message for log in state.parsed_logs]

            state.log_analysis = await self._log_analysis_agent.run(state.parsed_logs)
            state.status = WorkflowStatus.LOGS_ANALYZED

            await self._run_analysis_loop(state)

            if state.rca_report is None:
                raise ValueError("workflow could not generate RCA report")

            state.solution_recommendation = await self._solution_recommendation_agent.run(
                state.rca_report
            )
            state.status = WorkflowStatus.SOLUTION_RECOMMENDED

            written_paths = await self._report_writer_agent.run(
                ReportWriterInput(
                    report=state.rca_report,
                    solution=state.solution_recommendation,
                )
            )
            state.final_report_path = written_paths[0]
            state.status = WorkflowStatus.REPORT_SAVED

            return state
        except Exception as exc:
            state.add_error(str(exc))
            return state

    async def _run_analysis_loop(self, state: WorkflowState) -> None:
        retry_reason: str | None = None
        missing_evidence_hints: list[str] = []

        while True:
            await self._plan_and_retrieve_context(
                state=state,
                retry_reason=retry_reason,
                missing_evidence_hints=missing_evidence_hints,
            )

            await self._generate_and_evaluate_rca(state)

            if state.evidence_evaluation is None:
                raise ValueError("workflow could not evaluate RCA evidence")

            should_retry = (
                state.evidence_evaluation.retry_required
                and state.evidence_evaluation.confidence_score
                < state.confidence_threshold
                and state.can_retry()
            )

            if not should_retry:
                return

            state.increment_retry()
            retry_reason = state.evidence_evaluation.reason
            missing_evidence_hints = [
                *state.evidence_evaluation.missing_evidence,
                *state.evidence_evaluation.improved_code_queries,
                *state.evidence_evaluation.improved_knowledge_queries,
            ]

    async def _plan_and_retrieve_context(
        self,
        *,
        state: WorkflowState,
        retry_reason: str | None,
        missing_evidence_hints: list[str],
    ) -> None:
        if state.log_analysis is None:
            raise ValueError("workflow cannot plan context without log analysis")

        state.context_plan = await self._context_planning_agent.run(
            ContextPlanningInput(
                incident=state.incident,
                log_analysis=state.log_analysis,
                retry_reason=retry_reason,
                previous_missing_evidence_hints=missing_evidence_hints,
            )
        )
        state.status = WorkflowStatus.CONTEXT_PLANNED

        state.code_context = await self._code_context_agent.run(
            CodeContextInput(
                context_plan=state.context_plan,
                limit=self._code_context_limit,
            )
        )
        state.knowledge_context = await self._knowledge_base_agent.run(
            KnowledgeBaseInput(
                context_plan=state.context_plan,
                limit=self._knowledge_context_limit,
            )
        )
        state.status = WorkflowStatus.CONTEXT_RETRIEVED

    async def _generate_and_evaluate_rca(self, state: WorkflowState) -> None:
        if state.log_analysis is None:
            raise ValueError("workflow cannot generate hypotheses without log analysis")

        state.hypotheses = await self._hypothesis_agent.run(
            HypothesisInput(
                incident=state.incident,
                log_analysis=state.log_analysis,
                code_contexts=state.code_context,
                knowledge_contexts=state.knowledge_context,
            )
        )
        state.status = WorkflowStatus.HYPOTHESES_GENERATED

        state.rca_report = await self._rca_agent.run(
            RCAInput(
                incident=state.incident,
                log_analysis=state.log_analysis,
                hypotheses=state.hypotheses,
                code_contexts=state.code_context,
                knowledge_contexts=state.knowledge_context,
            )
        )
        state.status = WorkflowStatus.RCA_GENERATED

        state.evidence_evaluation = await self._evidence_evaluator_agent.run(
            state.rca_report
        )

    async def _get_logs(self, incident_id: str) -> list[LogEntry]:
        result = self._log_provider.get_logs(incident_id)
        if inspect.isawaitable(result):
            return await cast(Awaitable[list[LogEntry]], result)
        return result