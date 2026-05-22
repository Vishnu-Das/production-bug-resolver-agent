"""Supervisor agent that chooses the next specialist in the dynamic investigation."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.llm.base import LLMClient
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.orchestration import AgentDecision, AgentName
from bug_resolver.schemas.workflow_state import WorkflowState
from bug_resolver.utils.ids import new_agent_decision_id
from bug_resolver.prompts import SupervisorPromptBuilder


class SupervisorRoutingOutput(StrictBaseModel):
    """Structured LLM response that becomes a supervisor routing decision."""

    next_agent: AgentName
    reason: str = Field(..., min_length=1)
    queries: list[str]
    expected_evidence: list[str]
    should_continue: bool


class SupervisorAgent(BaseAgent[WorkflowState, AgentDecision]):
    """
    Chooses the next specialist agent for a dynamic investigation.

    The supervisor decides routing only. It does not fetch logs/code/docs,
    generate the RCA, save reports, or bypass guardrails.
    """

    name = "supervisor_agent"

    def __init__(self, llm_client: LLMClient, prompt_builder: SupervisorPromptBuilder | None = None,) -> None:
        self._llm_client = llm_client
        self._prompt_builder = prompt_builder or SupervisorPromptBuilder()

    async def _run(self, input_data: WorkflowState) -> AgentDecision:
        routing_output = await self._llm_client.generate_structured(
            self._build_prompt(input_data),
            SupervisorRoutingOutput,
            system_prompt=self._build_system_prompt(),
        )

        return AgentDecision(
            decision_id=new_agent_decision_id(),
            next_agent=routing_output.next_agent,
            reason=routing_output.reason,
            queries=routing_output.queries,
            expected_evidence=routing_output.expected_evidence,
            should_continue=routing_output.should_continue,
            metadata={},
        )

    def _build_system_prompt(self) -> str:
        return self._prompt_builder.build_system_prompt()

    def _build_prompt(self, state: WorkflowState) -> str:
        incident = state.incident
        evidence_summary = self._format_evidence_summary(state)
        previous_decisions = self._format_previous_decisions(state)
        evaluation_summary = self._format_evaluation_summary(state)
        allowed_agents = ", ".join(agent.value for agent in state.allowed_agent_names)

        return (
            "Decide the next investigation step.\n\n"
            f"Incident ID: {incident.incident_id}\n"
            f"Title: {incident.title}\n"
            f"Description: {incident.description}\n"
            f"Severity: {incident.severity.value}\n"
            f"Affected service: {incident.affected_service or 'unknown'}\n\n"
            f"Investigation status: {state.investigation_status.value}\n"
            f"Evidence count: {len(state.evidence_items)}\n"
            f"Minimum evidence before RCA: {state.minimum_evidence_count_before_rca}\n"
            f"Replans: {state.replan_count}/{state.max_replans}\n"
            f"Steps: {len(state.trace.steps)}/{state.max_steps}\n"
            f"Allowed agents: {allowed_agents}\n\n"
            f"Evidence summary:\n{evidence_summary}\n\n"
            f"Evidence evaluation:\n{evaluation_summary}\n\n"
            f"Previous supervisor decisions:\n{previous_decisions}\n\n"
            "Return the best next agent, a concise reason, useful queries or "
            "instructions for that agent, expected evidence, and whether the "
            "workflow should continue."
        )

    def _format_evidence_summary(self, state: WorkflowState) -> str:
        if not state.evidence_items:
            return "- No evidence has been collected yet."

        lines: list[str] = []
        for evidence in state.evidence_items:
            location = evidence.source_name
            if evidence.file_path:
                location = evidence.file_path
            if evidence.line_start and evidence.line_end:
                location = f"{location}:{evidence.line_start}-{evidence.line_end}"

            lines.append(
                f"- {evidence.evidence_id} [{evidence.source_type.value}] "
                f"{location}: {evidence.content}"
            )

        return "\n".join(lines)

    def _format_previous_decisions(self, state: WorkflowState) -> str:
        if not state.trace.decisions:
            return "- No previous supervisor decisions."

        return "\n".join(
            (f"- {decision.decision_id}: {decision.next_agent.value} because {decision.reason}")
            for decision in state.trace.decisions
        )

    def _format_evaluation_summary(self, state: WorkflowState) -> str:
        if state.evidence_evaluation is None:
            return "- Evidence has not been evaluated yet."

        evaluation = state.evidence_evaluation
        missing_evidence = ", ".join(evaluation.missing_evidence) or "none"
        return (
            f"- confidence={evaluation.confidence_score}; "
            f"retry_required={evaluation.retry_required}; "
            f"missing_evidence={missing_evidence}; reason={evaluation.reason}"
        )
