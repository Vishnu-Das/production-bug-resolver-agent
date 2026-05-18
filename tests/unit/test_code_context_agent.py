from __future__ import annotations

import pytest

from bug_resolver.agents import CodeContextAgent, CodeContextInput
from bug_resolver.schemas import CodeContext, ContextPlan


class FakeCodeContextProvider:
    def __init__(self) -> None:
        self.received_queries: list[str] = []
        self.received_limit: int | None = None

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        self.received_queries = queries
        self.received_limit = limit

        return [
            CodeContext(
                context_id="ctx-001",
                file_path="src/rag/other.py",
                snippet="def other(): pass",
                function_name="other",
                retrieval_query="other",
                relevance_score=0.95,
            ),
            CodeContext(
                context_id="ctx-002",
                file_path="src/rag/llm.py",
                snippet="def route(): return response['output']",
                line_start=18,
                line_end=18,
                function_name="route",
                retrieval_query="src/rag/llm.py route",
                relevance_score=0.80,
            ),
        ]


@pytest.mark.asyncio
async def test_code_context_agent_searches_provider_using_context_plan() -> None:
    provider = FakeCodeContextProvider()
    agent = CodeContextAgent(code_context_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-001",
        code_search_queries=["KeyError", "'output'"],
        knowledge_search_queries=[],
        files_to_prioritize=["src/rag/llm.py"],
        functions_to_prioritize=["route"],
        generated_from="incident+exception+stack_trace",
    )

    result = await agent.run(
        CodeContextInput(
            context_plan=context_plan,
            limit=5,
        )
    )

    assert provider.received_limit == 5
    assert provider.received_queries == [
        "KeyError",
        "'output'",
        "src/rag/llm.py",
        "route",
        "src/rag/llm.py route",
    ]

    assert len(result) == 2
    assert result[0].context_id == "ctx-002"
    assert result[0].file_path == "src/rag/llm.py"
    assert result[0].function_name == "route"


@pytest.mark.asyncio
async def test_code_context_agent_returns_empty_when_no_queries() -> None:
    provider = FakeCodeContextProvider()
    agent = CodeContextAgent(code_context_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-002",
        code_search_queries=[],
        knowledge_search_queries=[],
        files_to_prioritize=[],
        functions_to_prioritize=[],
        generated_from="incident",
    )

    result = await agent.run(
        CodeContextInput(
            context_plan=context_plan,
            limit=5,
        )
    )

    assert result == []
    assert provider.received_queries == []
    assert provider.received_limit is None


@pytest.mark.asyncio
async def test_code_context_agent_limits_results() -> None:
    provider = FakeCodeContextProvider()
    agent = CodeContextAgent(code_context_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-003",
        code_search_queries=["KeyError"],
        knowledge_search_queries=[],
        files_to_prioritize=[],
        functions_to_prioritize=[],
        generated_from="incident+exception",
    )

    result = await agent.run(
        CodeContextInput(
            context_plan=context_plan,
            limit=1,
        )
    )

    assert len(result) == 1
    assert provider.received_limit == 1


@pytest.mark.asyncio
async def test_code_context_agent_deduplicates_queries() -> None:
    provider = FakeCodeContextProvider()
    agent = CodeContextAgent(code_context_provider=provider)

    context_plan = ContextPlan(
        plan_id="CTX-004",
        code_search_queries=["KeyError", "KeyError", "src/rag/llm.py"],
        knowledge_search_queries=[],
        files_to_prioritize=["src/rag/llm.py"],
        functions_to_prioritize=["route", "route"],
        generated_from="incident+exception",
    )

    await agent.run(
        CodeContextInput(
            context_plan=context_plan,
            limit=5,
        )
    )

    assert provider.received_queries == [
        "KeyError",
        "src/rag/llm.py",
        "route",
        "src/rag/llm.py route",
    ]