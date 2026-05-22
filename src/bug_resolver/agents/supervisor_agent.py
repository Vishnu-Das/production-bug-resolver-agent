"""Supervisor agent that chooses the next specialist in the dynamic investigation."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.llm.base import LLMClient
from bug_resolver.prompts import SupervisorPromptBuilder
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.orchestration import AgentDecision, AgentName
from bug_resolver.schemas.workflow_state import WorkflowState
from bug_resolver.utils.ids import new_agent_decision_id


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

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_builder: SupervisorPromptBuilder | None = None,
    ) -> None:
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
        return self._prompt_builder.build_user_prompt(state)
