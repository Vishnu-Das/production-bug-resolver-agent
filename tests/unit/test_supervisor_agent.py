from __future__ import annotations

from pydantic import BaseModel
import pytest

from bug_resolver.agents import SupervisorAgent, SupervisorRoutingOutput
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    EvidenceItem,
    EvidenceSourceType,
    Incident,
    WorkflowState,
)


class FakeLLMClient:
    def __init__(self, output: SupervisorRoutingOutput) -> None:
        self.output = output
        self.prompt: str | None = None
        self.system_prompt: str | None = None
        self.output_schema: type[BaseModel] | None = None

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        raise AssertionError("SupervisorAgent should request structured output")

    async def generate_structured(
        self,
        prompt: str,
        output_schema: type[BaseModel],
        *,
        system_prompt: str | None = None,
    ) -> BaseModel:
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.output_schema = output_schema
        return self.output


def make_state() -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Summary route fails",
            description="Users get 500 errors when asking summary questions.",
            affected_service="conversational_rag",
        )
    )


@pytest.mark.asyncio
async def test_supervisor_agent_returns_structured_agent_decision() -> None:
    llm = FakeLLMClient(
        SupervisorRoutingOutput(
            next_agent=AgentName.LOG_INVESTIGATOR,
            reason="Runtime evidence is missing.",
            queries=["INC-001 logs"],
            expected_evidence=["exception type", "stack trace"],
            should_continue=True,
        )
    )
    agent = SupervisorAgent(llm)

    decision = await agent.run(make_state())

    assert isinstance(decision, AgentDecision)
    assert decision.decision_id.startswith("DEC-")
    assert decision.next_agent == AgentName.LOG_INVESTIGATOR
    assert decision.reason == "Runtime evidence is missing."
    assert decision.queries == ["INC-001 logs"]
    assert decision.expected_evidence == ["exception type", "stack trace"]
    assert decision.should_continue is True
    assert llm.output_schema is SupervisorRoutingOutput
    assert llm.system_prompt is not None
    assert "Choose exactly one next specialist agent" in llm.system_prompt


@pytest.mark.asyncio
async def test_supervisor_agent_can_route_to_code_investigator() -> None:
    state = make_state()
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="TypeError in src/rag/router.py route_query",
            file_path="src/rag/router.py",
            line_start=42,
            line_end=42,
        )
    )
    llm = FakeLLMClient(
        SupervisorRoutingOutput(
            next_agent=AgentName.CODE_INVESTIGATOR,
            reason="Logs point to a concrete router file and function.",
            queries=["src/rag/router.py route_query TypeError"],
            expected_evidence=["failing function", "response schema"],
            should_continue=True,
        )
    )
    agent = SupervisorAgent(llm)

    decision = await agent.run(state)

    assert decision.next_agent == AgentName.CODE_INVESTIGATOR
    assert "router.py" in decision.queries[0]
    assert llm.prompt is not None
    assert "ev-log-1 [log] src/rag/router.py:42-42" in llm.prompt


@pytest.mark.asyncio
async def test_supervisor_agent_can_route_to_knowledge_base_investigator() -> None:
    llm = FakeLLMClient(
        SupervisorRoutingOutput(
            next_agent=AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
            reason="Expected routing behavior is unclear.",
            queries=["summary routing expected behavior"],
            expected_evidence=["design intent", "documented routing contract"],
            should_continue=True,
        )
    )
    agent = SupervisorAgent(llm)

    decision = await agent.run(make_state())

    assert decision.next_agent == AgentName.KNOWLEDGE_BASE_INVESTIGATOR
    assert decision.expected_evidence == ["design intent", "documented routing contract"]


@pytest.mark.asyncio
async def test_supervisor_agent_prompt_includes_dynamic_state() -> None:
    state = make_state()
    previous_decision = AgentDecision(
        decision_id="decision-previous",
        next_agent=AgentName.LOG_INVESTIGATOR,
        reason="Need logs first.",
        queries=["INC-001 logs"],
    )
    state.record_decision(previous_decision)
    state.increment_replan()

    llm = FakeLLMClient(
        SupervisorRoutingOutput(
            next_agent=AgentName.CODE_INVESTIGATOR,
            reason="Use logs to fetch code.",
            queries=[],
            expected_evidence=[],
            should_continue=True,
        )
    )
    agent = SupervisorAgent(llm)

    await agent.run(state)

    assert llm.prompt is not None
    assert "Incident ID: INC-001" in llm.prompt
    assert "Affected service: conversational_rag" in llm.prompt
    assert "Replans: 1/2" in llm.prompt
    assert "Allowed agents:" in llm.prompt
    assert "decision-previous: log_investigator because Need logs first." in llm.prompt


@pytest.mark.asyncio
async def test_supervisor_agent_rejects_empty_input() -> None:
    llm = FakeLLMClient(
        SupervisorRoutingOutput(
            next_agent=AgentName.LOG_INVESTIGATOR,
            reason="Need logs.",
            queries=[],
            expected_evidence=[],
            should_continue=True,
        )
    )
    agent = SupervisorAgent(llm)

    with pytest.raises(ValueError, match="supervisor_agent received empty input"):
        await agent.run(None)  # type: ignore[arg-type]
