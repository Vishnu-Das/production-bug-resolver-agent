"""Shared workflow trace and execution recording helpers."""

from __future__ import annotations

from bug_resolver.schemas import (
    AgentDecision,
    AgentExecutionRecord,
    AgentRunStatus,
    EvidenceItem,
    GuardrailDecision,
    InvestigationStep,
    WorkflowState,
)
from bug_resolver.utils.ids import new_agent_execution_id


class WorkflowExecutionRecorder:
    """Record evidence, executions, and trace steps for workflow implementations."""

    def record_successful_evidence_run(
        self,
        state: WorkflowState,
        decision: AgentDecision,
        evidence_items: list[EvidenceItem],
    ) -> None:
        for evidence in evidence_items:
            state.add_evidence(evidence)

        self.record_successful_agent_run(
            state=state,
            decision=decision,
            evidence_ids=[evidence.evidence_id for evidence in evidence_items],
            output_summary=f"Collected {len(evidence_items)} evidence item(s).",
        )

    def record_successful_agent_run(
        self,
        *,
        state: WorkflowState,
        decision: AgentDecision,
        evidence_ids: list[str],
        output_summary: str,
    ) -> None:
        execution = AgentExecutionRecord(
            execution_id=new_agent_execution_id(),
            agent_name=decision.next_agent,
            status=AgentRunStatus.SUCCEEDED,
            decision_id=decision.decision_id,
            output_summary=output_summary,
            evidence_ids=evidence_ids,
        )
        state.record_agent_execution(execution)
        state.add_investigation_step(
            InvestigationStep(
                step_number=state.trace.next_step_number(),
                agent_name=decision.next_agent,
                run_status=AgentRunStatus.SUCCEEDED,
                decision_id=decision.decision_id,
                execution_id=execution.execution_id,
                evidence_ids=evidence_ids,
            )
        )

    def record_blocked_guardrail_step(
        self,
        *,
        state: WorkflowState,
        decision: AgentDecision,
        guardrail_decision: GuardrailDecision,
    ) -> None:
        state.add_investigation_step(
            InvestigationStep(
                step_number=state.trace.next_step_number(),
                agent_name=decision.next_agent,
                run_status=AgentRunStatus.BLOCKED,
                decision_id=decision.decision_id,
                guardrail_id=guardrail_decision.guardrail_id,
                notes=[guardrail_decision.reason],
            )
        )

    def record_blocked_unsupported_agent(
        self,
        state: WorkflowState,
        decision: AgentDecision,
    ) -> None:
        execution = AgentExecutionRecord(
            execution_id=new_agent_execution_id(),
            agent_name=decision.next_agent,
            status=AgentRunStatus.BLOCKED,
            decision_id=decision.decision_id,
            output_summary="Agent execution is not wired in this workflow slice.",
        )
        state.record_agent_execution(execution)
        state.add_investigation_step(
            InvestigationStep(
                step_number=state.trace.next_step_number(),
                agent_name=decision.next_agent,
                run_status=AgentRunStatus.BLOCKED,
                decision_id=decision.decision_id,
                execution_id=execution.execution_id,
                notes=["Agent execution is not wired in this workflow slice."],
            )
        )
