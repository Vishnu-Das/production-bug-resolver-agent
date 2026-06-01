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
from bug_resolver.providers.incident import IncidentProvider
from bug_resolver.rules import GuardrailEngine
from bug_resolver.errors import normalize_error
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    EvidenceItem,
    InvestigationStatus,
    WorkflowState,
)
from bug_resolver.utils.ids import new_agent_decision_id
from bug_resolver.utils.observability import get_logger, traceable
from bug_resolver.workflows.workflow_execution_recorder import WorkflowExecutionRecorder


logger = get_logger(__name__)


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

    @traceable(name="workflow.manual.run", run_type="chain")
    async def run(self, incident_id: str) -> WorkflowState:
        logger.info("manual workflow started incident_id=%s", incident_id)
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
                logger.info(
                    "manual workflow decision incident_id=%s decision_id=%s next_agent=%s",
                    incident_id,
                    decision.decision_id,
                    decision.next_agent.value,
                )

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
                    if not state.can_take_step():
                        state.mark_low_confidence()
                        state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
                        return state
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
                        await self._execute_decision_safely(
                            state=state,
                            decision=fallback_decision,
                        )
                        if state.investigation_status == InvestigationStatus.FAILED:
                            return state
                        if state.investigation_status == InvestigationStatus.COMPLETED:
                            return state
                        if await self._finalize_if_ready(state):
                            return state
                    continue

                if decision.next_agent == AgentName.FINISH:
                    state.investigation_status = InvestigationStatus.COMPLETED
                    return state

                await self._execute_decision_safely(state=state, decision=decision)

                if state.investigation_status == InvestigationStatus.FAILED:
                    return state
                if state.investigation_status == InvestigationStatus.COMPLETED:
                    return state
                if await self._finalize_if_ready(state):
                    return state

            state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
            state.mark_low_confidence()
            logger.info(
                "manual workflow finished incident_id=%s status=%s evidence_count=%s steps=%s",
                incident_id,
                state.investigation_status.value,
                len(state.evidence_items),
                len(state.trace.steps),
            )
            return state
        except Exception as exc:
            logger.exception("manual workflow failed incident_id=%s", incident_id)
            state.add_error(
                normalize_error(
                    exc,
                    component="workflow.manual",
                    context={"incident_id": incident_id},
                )
            )
            return state

    async def _execute_decision_safely(
        self,
        *,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> None:
        try:
            await self._execute_decision(state=state, decision=decision)
        except Exception as exc:
            recoverable = self._is_recoverable_agent_failure(decision.next_agent)
            error = normalize_error(
                exc,
                component=decision.next_agent.value,
                recoverable=recoverable,
                context={
                    "incident_id": state.incident.incident_id,
                    "decision_id": decision.decision_id,
                    "agent": decision.next_agent.value,
                },
            )
            state.add_error(error)
            self._execution_recorder.record_failed_agent_run(
                state=state,
                decision=decision,
                error_message=error.user_message,
                recoverable=error.recoverable,
            )

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
                    incident=state.incident,
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

        if decision.next_agent == AgentName.PATCH_SUGGESTER:
            if state.rca_report is None:
                raise ValueError("patch suggestion requires RCA report")
            if state.solution_recommendation is None:
                raise ValueError("patch suggestion requires solution recommendation")
            if self._patch_suggestion_agent is None:
                self._record_blocked_unsupported_agent(state, decision)
                return

            state.patch_suggestion = await self._patch_suggestion_agent.run(
                PatchSuggestionInput(
                    rca_report=state.rca_report,
                    solution_recommendation=state.solution_recommendation,
                )
            )
            self._record_successful_agent_run(
                state=state,
                decision=decision,
                evidence_ids=state.patch_suggestion.evidence_ids,
                output_summary=state.patch_suggestion.summary,
            )
            return

        if decision.next_agent == AgentName.PATCH_GENERATOR:
            if state.rca_report is None:
                raise ValueError("patch generation requires RCA report")
            if state.solution_recommendation is None:
                raise ValueError("patch generation requires solution recommendation")
            if state.patch_suggestion is None:
                raise ValueError("patch generation requires patch suggestion")
            if self._patch_generator_agent is None:
                self._record_blocked_unsupported_agent(state, decision)
                return

            generation_result = await self._patch_generator_agent.run(
                PatchGeneratorInput(
                    rca_report=state.rca_report,
                    solution_recommendation=state.solution_recommendation,
                    affected_files=state.patch_suggestion.affected_files,
                    evidence_ids=state.patch_suggestion.evidence_ids,
                )
            )
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
            return

        if decision.next_agent == AgentName.REPORT_WRITER:
            if state.rca_report is None:
                raise ValueError("report writing requires RCA report")
            written_paths = await self._report_writer_agent.run(
                ReportWriterInput(
                    report=state.rca_report,
                    solution=state.solution_recommendation,
                    patch_suggestion=state.patch_suggestion,
                )
            )
            state.final_report_path = written_paths[0]
            state.report_artifact_paths = written_paths
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
            if state.can_take_step():
                self._execution_recorder.record_blocked_guardrail_step(
                    state=state,
                    decision=decision,
                    guardrail_decision=guardrail_decision,
                )
            state.mark_low_confidence()
            state.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
            return

        await self._execute_decision_safely(state=state, decision=decision)

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
            await self._execute_decision_safely(state=state, decision=rca_decision)
            if state.investigation_status == InvestigationStatus.FAILED:
                return False

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
            await self._execute_decision_safely(
                state=state,
                decision=solution_decision,
            )
            if state.investigation_status == InvestigationStatus.FAILED:
                return False

        if (
            self._include_patch_plan
            and state.patch_suggestion is None
            and state.rca_report is not None
            and state.solution_recommendation is not None
        ):
            patch_decision = AgentDecision(
                decision_id=new_agent_decision_id(),
                next_agent=AgentName.PATCH_SUGGESTER,
                reason="Optional patch suggestion requested; generate analyze-only patch plan.",
                queries=[],
                expected_evidence=[],
                should_continue=True,
                metadata={"forced_by_workflow": "true"},
            )
            state.record_decision(patch_decision)
            await self._execute_decision_safely(state=state, decision=patch_decision)
            if state.investigation_status == InvestigationStatus.FAILED:
                return False

        if (
            self._include_patch_diff
            and state.patch_suggestion is not None
            and not state.patch_suggestion.file_patches
            and not state.patch_suggestion.test_patches
        ):
            patch_generator_decision = AgentDecision(
                decision_id=new_agent_decision_id(),
                next_agent=AgentName.PATCH_GENERATOR,
                reason="Optional patch diff requested; generate analyze-only unified diffs.",
                queries=[],
                expected_evidence=[],
                should_continue=True,
                metadata={"forced_by_workflow": "true"},
            )
            state.record_decision(patch_generator_decision)
            await self._execute_decision_safely(
                state=state,
                decision=patch_generator_decision,
            )
            if state.investigation_status == InvestigationStatus.FAILED:
                return False

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
            await self._execute_decision_safely(state=state, decision=report_decision)

        return state.investigation_status == InvestigationStatus.COMPLETED

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
