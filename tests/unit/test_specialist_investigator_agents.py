"""Tests for log, code, and knowledge-base specialist agents."""

from __future__ import annotations

import pytest

from bug_resolver.agents import (
    CodeInvestigatorAgent,
    CodeInvestigatorInput,
    KnowledgeBaseInvestigatorAgent,
    KnowledgeBaseInvestigatorInput,
    LogInvestigatorAgent,
    LogInvestigatorInput,
)
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    CodeContext,
    EvidenceSourceType,
    KnowledgeContext,
    LogEntry,
    LogLevel,
)


def make_decision(
    agent_name: AgentName,
    queries: list[str] | None = None,
) -> AgentDecision:
    return AgentDecision(
        decision_id="decision-1",
        next_agent=agent_name,
        reason="Need more evidence.",
        queries=queries or [],
        expected_evidence=["useful evidence"],
    )


class FakeLogProvider:
    def __init__(self) -> None:
        self.incident_id: str | None = None

    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        self.incident_id = incident_id
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


class FakeCodeContextProvider:
    def __init__(self) -> None:
        self.queries: list[str] | None = None
        self.limit: int | None = None

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        self.queries = queries
        self.limit = limit
        return [
            CodeContext(
                context_id="code-1",
                file_path="src/rag/router.py",
                function_name="route_query",
                line_start=40,
                line_end=45,
                snippet="def route_query(...): return response['output']",
                relevance_score=0.91,
            )
        ]


class FakeKnowledgeBaseProvider:
    def __init__(self) -> None:
        self.queries: list[str] | None = None
        self.limit: int | None = None

    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        self.queries = queries
        self.limit = limit
        return [
            KnowledgeContext(
                context_id="kb-1",
                document_name="README.md",
                section_title="Routing",
                content="The router returns a structured response.",
                relevance_score=0.82,
            )
        ]


@pytest.mark.asyncio
async def test_log_investigator_agent_returns_log_evidence() -> None:
    provider = FakeLogProvider()
    agent = LogInvestigatorAgent(provider)
    decision = make_decision(AgentName.LOG_INVESTIGATOR)

    evidence = await agent.run(
        LogInvestigatorInput(
            incident_id="INC-001",
            decision=decision,
        )
    )

    assert provider.incident_id == "INC-001"
    assert len(evidence) == 1
    assert evidence[0].source_type == EvidenceSourceType.LOG
    assert evidence[0].source_name == "log-1"
    assert "TypeError: expected dict response" in evidence[0].content
    assert evidence[0].metadata["agent_name"] == "log_investigator_agent"
    assert evidence[0].metadata["decision_id"] == "decision-1"


@pytest.mark.asyncio
async def test_code_investigator_agent_uses_supervisor_queries() -> None:
    provider = FakeCodeContextProvider()
    agent = CodeInvestigatorAgent(provider)
    decision = make_decision(
        AgentName.CODE_INVESTIGATOR,
        queries=["router.py route_query TypeError"],
    )

    evidence = await agent.run(
        CodeInvestigatorInput(
            decision=decision,
            limit=3,
        )
    )

    assert provider.queries == ["router.py route_query TypeError"]
    assert provider.limit == 3
    assert len(evidence) == 1
    assert evidence[0].source_type == EvidenceSourceType.CODE
    assert evidence[0].file_path == "src/rag/router.py"
    assert evidence[0].line_start == 40
    assert evidence[0].metadata["agent_name"] == "code_investigator_agent"
    assert evidence[0].metadata["decision_id"] == "decision-1"


@pytest.mark.asyncio
async def test_code_investigator_agent_falls_back_to_decision_reason() -> None:
    provider = FakeCodeContextProvider()
    agent = CodeInvestigatorAgent(provider)
    decision = make_decision(AgentName.CODE_INVESTIGATOR)

    await agent.run(CodeInvestigatorInput(decision=decision))

    assert provider.queries == ["Need more evidence."]


@pytest.mark.asyncio
async def test_knowledge_base_investigator_agent_uses_supervisor_queries() -> None:
    provider = FakeKnowledgeBaseProvider()
    agent = KnowledgeBaseInvestigatorAgent(provider)
    decision = make_decision(
        AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
        queries=["router expected response design"],
    )

    evidence = await agent.run(
        KnowledgeBaseInvestigatorInput(
            decision=decision,
            limit=2,
        )
    )

    assert provider.queries == ["router expected response design"]
    assert provider.limit == 2
    assert len(evidence) == 1
    assert evidence[0].source_type == EvidenceSourceType.KNOWLEDGE_BASE
    assert evidence[0].source_name == "README.md"
    assert evidence[0].metadata["section_title"] == "Routing"
    assert evidence[0].metadata["agent_name"] == "knowledge_base_investigator_agent"
    assert evidence[0].metadata["decision_id"] == "decision-1"


@pytest.mark.asyncio
async def test_knowledge_base_investigator_agent_falls_back_to_decision_reason() -> None:
    provider = FakeKnowledgeBaseProvider()
    agent = KnowledgeBaseInvestigatorAgent(provider)
    decision = make_decision(AgentName.KNOWLEDGE_BASE_INVESTIGATOR)

    await agent.run(KnowledgeBaseInvestigatorInput(decision=decision))

    assert provider.queries == ["Need more evidence."]
