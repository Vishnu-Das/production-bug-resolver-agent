from __future__ import annotations

import pytest

from bug_resolver.agents import KnowledgeBaseAgent, KnowledgeBaseInput
from bug_resolver.schemas import ContextPlan, KnowledgeContext


class FakeKnowledgeBaseProvider:
    def __init__(self) -> None:
        self.received_queries: list[str] = []
        self.received_limit: int | None = None

    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        self.received_queries = queries
        self.received_limit = limit

        return [
            KnowledgeContext(
                context_id="kb-001",
                document_name="README.md",
                content="The app supports conversational retrieval and summary queries.",
                section_title="Features",
                file_path="README.md",
                retrieval_query="summary flow",
                relevance_score=0.90,
            ),
            KnowledgeContext(
                context_id="kb-002",
                document_name="troubleshooting.md",
                content="For KeyError output failures, inspect router structured output.",
                section_title="Known Issues",
                file_path="docs/troubleshooting.md",
                retrieval_query="KeyError troubleshooting",
                relevance_score=0.80,
            ),
        ]


@pytest.mark.asyncio
async def test_knowledge_base_agent_searches_provider_using_context_plan() -> None:
    provider = FakeKnowledgeBaseProvider()
    agent = KnowledgeBaseAgent(knowledge_base_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-001",
        code_search_queries=[],
        knowledge_search_queries=[
            "summary flow",
            "KeyError troubleshooting",
        ],
        files_to_prioritize=[],
        functions_to_prioritize=["route"],
        generated_from="incident+exception",
    )

    result = await agent.run(
        KnowledgeBaseInput(
            context_plan=context_plan,
            limit=5,
        )
    )

    assert provider.received_limit == 5
    assert provider.received_queries == [
        "summary flow",
        "KeyError troubleshooting",
    ]

    assert len(result) == 2
    assert result[0].context_id == "kb-002"
    assert result[0].document_name == "troubleshooting.md"


@pytest.mark.asyncio
async def test_knowledge_base_agent_returns_empty_when_no_queries() -> None:
    provider = FakeKnowledgeBaseProvider()
    agent = KnowledgeBaseAgent(knowledge_base_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-002",
        code_search_queries=[],
        knowledge_search_queries=[],
        files_to_prioritize=[],
        functions_to_prioritize=[],
        missing_evidence_hints=[],
        generated_from="incident",
    )

    result = await agent.run(
        KnowledgeBaseInput(
            context_plan=context_plan,
            limit=5,
        )
    )

    assert result == []
    assert provider.received_queries == []
    assert provider.received_limit is None


@pytest.mark.asyncio
async def test_knowledge_base_agent_includes_missing_evidence_hints_as_queries() -> None:
    provider = FakeKnowledgeBaseProvider()
    agent = KnowledgeBaseAgent(knowledge_base_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-003",
        code_search_queries=[],
        knowledge_search_queries=["summary flow"],
        files_to_prioritize=[],
        functions_to_prioritize=[],
        missing_evidence_hints=[
            "Need expected behavior for summary queries.",
        ],
        generated_from="incident",
    )

    await agent.run(
        KnowledgeBaseInput(
            context_plan=context_plan,
            limit=5,
        )
    )

    assert provider.received_queries == [
        "summary flow",
        "Need expected behavior for summary queries.",
    ]


@pytest.mark.asyncio
async def test_knowledge_base_agent_limits_results() -> None:
    provider = FakeKnowledgeBaseProvider()
    agent = KnowledgeBaseAgent(knowledge_base_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-004",
        code_search_queries=[],
        knowledge_search_queries=["summary flow"],
        files_to_prioritize=[],
        functions_to_prioritize=[],
        generated_from="incident",
    )

    result = await agent.run(
        KnowledgeBaseInput(
            context_plan=context_plan,
            limit=1,
        )
    )

    assert len(result) == 1
    assert provider.received_limit == 1


@pytest.mark.asyncio
async def test_knowledge_base_agent_deduplicates_queries() -> None:
    provider = FakeKnowledgeBaseProvider()
    agent = KnowledgeBaseAgent(knowledge_base_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-005",
        code_search_queries=[],
        knowledge_search_queries=[
            "summary flow",
            "summary flow",
        ],
        files_to_prioritize=[],
        functions_to_prioritize=[],
        missing_evidence_hints=[
            "summary flow",
            "Need expected behavior.",
        ],
        generated_from="incident",
    )

    await agent.run(
        KnowledgeBaseInput(
            context_plan=context_plan,
            limit=5,
        )
    )

    assert provider.received_queries == [
        "summary flow",
        "Need expected behavior.",
    ]