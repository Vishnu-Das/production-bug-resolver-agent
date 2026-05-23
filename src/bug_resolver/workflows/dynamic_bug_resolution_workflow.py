"""Supervisor-led dynamic investigation workflow with guardrails and replanning."""

from __future__ import annotations

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
    RCAWriterAgent,
    ReportWriterAgent,
    ReportWriterInput,
    SolutionRecommendationAgent,
    SupervisorAgent,
)
from bug_resolver.providers.incident import IncidentProvider
from bug_resolver.rules import GuardrailEngine
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    EvidenceItem,
    InvestigationStatus,
    WorkflowState,
)
from bug_resolver.utils.ids import new_agent_decision_id
from bug_resolver.workflows.workflow_execution_recorder import WorkflowExecutionRecorder


class DynamicBugResolutionWorkflow:
    """
    Supervisor-led dynamic investigation workflow.

    The workflow asks the supervisor for the next route, validates that route
    with deterministic guardrails, gathers evidence through specialist agents,
    and finalizes RCA, solution, and report artifacts once evidence is ready.
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
        code_graph_investigator_agent: CodeGraphInvestigatorAgent | None = None,
        historical_rca_investigator_agent: HistoricalRCAInvestigatorAgent | None = None,
        max_steps: int = 12,
        max_replans: int = 2,
        max_agent_invocations_per_agent: int = 3,
        confidence_threshold: float = 0.75,
        minimum_evidence_count_before_rca: int = 2,
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
        self._report_writer_agent = report_writer_agent
        self._max_steps = max_steps
        self._max_replans = max_replans
        self._max_agent_invocations_per_agent = max_agent_invocations_per_agent
        self._confidence_threshold = confidence_threshold
        self._minimum_evidence_count_before_rca = minimum_evidence_count_before_rca
        self._execution_recorder = WorkflowExecutionRecorder()

    async def run(self, incident_id: str) -> WorkflowState:
        incident = await self._incident_provider.get_incident(incident_id)
        state = WorkflowState(
            incident=incident,
            investigation_status=InvestigationStatus.RUNNING,
            max_steps=self._max_steps,
            max_replans=self._max_replans,
            max_agent_invocations_per_agent=self._max_agent_invocations_per_agent,
            confidence_threshold=self._confidence_threshold,
            minimum_evidence_count_before_rca=self._minimum_evidence_count_before_rca,
        )

        try:
            while state.can_take_step():
                decision = await self._supervisor_agent.run(state)
                state.record_decision(decision)

                guardrail_decision = self._guardrail_engine.validate_decision(
                    state=state,
                    decision=decision,
                )
                state.record_guardrail_decision(guardrail_decision)

                if not guardrail_decision.allowed:
                    self._execution_recorder.record_blocked_guardrail_step(
                        state=state,
                        decision=decision,
                        guardrail_decision=guardrail_decision,
                    )
                    if guardrail_decision.fallback_next_agent in {
                        AgentName.FINISH,
                        AgentName.EVIDENCE_EVALUATOR,
                    }:
                        state.mark_low_confidence()
                        return state
                    if guardrail_decision.fallback_next_agent is not None:
                        fallback_decision = AgentDecision(
                            decision_id=new_agent_decision_id(),
                            next_agent=guardrail_decision.fallback_next_agent,
                            reason=(
                                "Guardrail fallback after blocked decision: "
                                f"{guardrail_decision.reason}"
                            ),
                            queries=decision.queries,
                            expected_evidence=decision.expected_evidence,
                            should_continue=True,
                            metadata={"fallback_for": decision.decision_id},
                        )
                        state.record_decision(fallback_decision)
                        await self._execute_decision(
                            state=state,
                            decision=fallback_decision,
                        )
                        if state.investigation_status == InvestigationStatus.COMPLETED:
                            return state
                        if await self._finalize_if_ready(state):
                            return state
                    continue

                if decision.next_agent == AgentName.FINISH:
                    state.investigation_status = InvestigationStatus.COMPLETED
                    return state

                await self._execute_decision(state=state, decision=decision)

                if state.investigation_status == InvestigationStatus.COMPLETED:
                    return state
                if await self._finalize_if_ready(state):
                    return state

            state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
            state.mark_low_confidence()
            return state
        except Exception as exc:
            state.add_error(str(exc))
            return state

    async def _execute_decision(
        self,
        *,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> None:
        if decision.next_agent == AgentName.LOG_INVESTIGATOR:
            evidence_items = await self._log_investigator_agent.run(
                LogInvestigatorInput(
                    incident_id=state.incident.incident_id,
                    decision=decision,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            await self._run_evidence_evaluator(state)
            return

        if decision.next_agent == AgentName.CODE_INVESTIGATOR:
            evidence_items = await self._code_investigator_agent.run(
                CodeInvestigatorInput(
                    decision=decision,
                    evidence_items=state.evidence_items,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)

            # New: immediately re-check whether evidence is enough
            await self._run_evidence_evaluator(state)
            return

        if decision.next_agent == AgentName.GRAPH_INVESTIGATOR:
            if self._code_graph_investigator_agent is None:
                self._record_blocked_unsupported_agent(state, decision)
                return

            evidence_items = await self._code_graph_investigator_agent.run(
                CodeGraphInvestigatorInput(
                    decision=decision,
                    evidence_items=state.evidence_items,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            await self._run_evidence_evaluator(state)
            return

        if decision.next_agent == AgentName.HISTORICAL_RCA_INVESTIGATOR:
            if self._historical_rca_investigator_agent is None:
                self._record_blocked_unsupported_agent(state, decision)
                return

            evidence_items = await self._historical_rca_investigator_agent.run(
                HistoricalRCAInvestigatorInput(
                    incident_id=state.incident.incident_id,
                    decision=decision,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)
            await self._run_evidence_evaluator(state)
            return

        if decision.next_agent == AgentName.KNOWLEDGE_BASE_INVESTIGATOR:
            evidence_items = await self._knowledge_base_investigator_agent.run(
                KnowledgeBaseInvestigatorInput(
                    decision=decision,
                    limit=5,
                )
            )
            self._record_successful_evidence_run(state, decision, evidence_items)

            # New: immediately re-check whether evidence is enough
            await self._run_evidence_evaluator(state)
            return

        if decision.next_agent == AgentName.EVIDENCE_EVALUATOR:
            evaluation = await self._evidence_evaluator_agent.run(state)
            state.evidence_evaluation = evaluation
            if evaluation.retry_required and state.can_replan():
                state.increment_replan()
            self._record_successful_agent_run(
                state=state,
                decision=decision,
                evidence_ids=[],
                output_summary=evaluation.reason,
            )
            return

        if decision.next_agent == AgentName.RCA_WRITER:
            state.rca_report = await self._rca_writer_agent.run(state)
            self._record_successful_agent_run(
                state=state,
                decision=decision,
                evidence_ids=state.rca_report.evidence_ids,
                output_summary=f"Generated RCA report {state.rca_report.report_id}.",
            )
            return

        if decision.next_agent == AgentName.SOLUTION_RECOMMENDER:
            if state.rca_report is None:
                raise ValueError("solution recommendation requires RCA report")
            state.solution_recommendation = await self._solution_recommendation_agent.run(
                state.rca_report
            )
            self._record_successful_agent_run(
                state=state,
                decision=decision,
                evidence_ids=state.solution_recommendation.evidence_ids,
                output_summary=state.solution_recommendation.summary,
            )
            return

        if decision.next_agent == AgentName.REPORT_WRITER:
            if state.rca_report is None:
                raise ValueError("report writing requires RCA report")
            written_paths = await self._report_writer_agent.run(
                ReportWriterInput(
                    report=state.rca_report,
                    solution=state.solution_recommendation,
                )
            )
            state.final_report_path = written_paths[0]
            state.investigation_status = InvestigationStatus.COMPLETED
            self._record_successful_agent_run(
                state=state,
                decision=decision,
                evidence_ids=state.rca_report.evidence_ids,
                output_summary=f"Saved report to {written_paths[0]}.",
            )
            return

        self._record_blocked_unsupported_agent(state, decision)

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

    def _record_blocked_unsupported_agent(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> None:
        self._execution_recorder.record_blocked_unsupported_agent(state, decision)

    async def _run_evidence_evaluator(self, state: WorkflowState) -> None:
        decision = AgentDecision(
            decision_id=new_agent_decision_id(),
            next_agent=AgentName.EVIDENCE_EVALUATOR,
            reason="Evaluate evidence after latest investigation step.",
            queries=[],
            expected_evidence=[],
            should_continue=True,
            metadata={"forced_by_workflow": "true"},
        )

        state.record_decision(decision)

        guardrail_decision = self._guardrail_engine.validate_decision(
            state=state,
            decision=decision,
        )
        state.record_guardrail_decision(guardrail_decision)

        if not guardrail_decision.allowed:
            self._execution_recorder.record_blocked_guardrail_step(
                state=state,
                decision=decision,
                guardrail_decision=guardrail_decision,
            )
            return

        await self._execute_decision(state=state, decision=decision)

    async def _finalize_if_ready(self, state: WorkflowState) -> bool:
        """Run deterministic finalization path once evidence is sufficient.

        The supervisor controls evidence gathering. Once the evaluator says RCA can
        be written, the workflow should complete RCA -> solution -> report without
        asking the supervisor to choose more investigation agents.
        """
        if state.evidence_evaluation is None:
            return False

        if not state.evidence_evaluation.can_write_rca:
            return False

        if state.rca_report is None:
            rca_decision = AgentDecision(
                decision_id=new_agent_decision_id(),
                next_agent=AgentName.RCA_WRITER,
                reason="Evidence evaluation says RCA can be written.",
                queries=[],
                expected_evidence=[],
                should_continue=True,
                metadata={"forced_by_workflow": "true"},
            )
            state.record_decision(rca_decision)
            await self._execute_decision(state=state, decision=rca_decision)

        if state.solution_recommendation is None:
            solution_decision = AgentDecision(
                decision_id=new_agent_decision_id(),
                next_agent=AgentName.SOLUTION_RECOMMENDER,
                reason="RCA report is ready; generate solution recommendation.",
                queries=[],
                expected_evidence=[],
                should_continue=True,
                metadata={"forced_by_workflow": "true"},
            )
            state.record_decision(solution_decision)
            await self._execute_decision(state=state, decision=solution_decision)

        if state.final_report_path is None:
            report_decision = AgentDecision(
                decision_id=new_agent_decision_id(),
                next_agent=AgentName.REPORT_WRITER,
                reason="RCA and solution are ready; save final report.",
                queries=[],
                expected_evidence=[],
                should_continue=False,
                metadata={"forced_by_workflow": "true"},
            )
            state.record_decision(report_decision)
            await self._execute_decision(state=state, decision=report_decision)

        return state.investigation_status == InvestigationStatus.COMPLETED
