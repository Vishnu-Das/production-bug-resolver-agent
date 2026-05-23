"""Tests for the AST-backed code graph investigator agent."""

import pytest

from bug_resolver.agents import CodeGraphInvestigatorAgent, CodeGraphInvestigatorInput
from bug_resolver.schemas import AgentDecision, AgentName, CodeGraphContext


class FakeCodeGraphProvider:
    def __init__(self, contexts: list[CodeGraphContext]) -> None:
        self.contexts = contexts
        self.queries: list[str] | None = None
        self.limit: int | None = None

    async def search_graph(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeGraphContext]:
        self.queries = queries
        self.limit = limit
        return self.contexts[:limit]


def make_decision(queries: list[str] | None = None) -> AgentDecision:
    return AgentDecision(
        decision_id="decision-1",
        next_agent=AgentName.GRAPH_INVESTIGATOR,
        reason="Find callers for rerank_documents.",
        queries=queries or [],
        expected_evidence=["Call graph evidence"],
        should_continue=True,
    )


@pytest.mark.asyncio
async def test_code_graph_investigator_returns_graph_evidence() -> None:
    provider = FakeCodeGraphProvider(
        [
            CodeGraphContext(
                context_id="src/reranker.py:rerank_documents",
                file_path="src/reranker.py",
                relative_path="src/reranker.py",
                symbol_name="rerank_documents",
                symbol_type="function",
                qualified_symbol="rerank_documents",
                line_start=10,
                line_end=20,
                calls=["load_reranker"],
                called_by=["answer_question"],
                content=(
                    "src/reranker.py:rerank_documents is a function. "
                    "Calls: load_reranker. Called by: answer_question."
                ),
                relevance_score=0.9,
            )
        ]
    )

    agent = CodeGraphInvestigatorAgent(provider)
    decision = make_decision(["rerank_documents callers"])

    evidence_items = await agent.run(
        CodeGraphInvestigatorInput(
            decision=decision,
            limit=3,
        )
    )

    assert provider.queries is not None
    assert provider.queries[0] == "rerank_documents callers"
    assert provider.limit == 3
    assert evidence_items[0].evidence_id == "graph-src/reranker.py:rerank_documents"
    assert evidence_items[0].metadata["agent_name"] == "code_graph_investigator_agent"
    assert evidence_items[0].metadata["decision_id"] == "decision-1"
    assert evidence_items[0].metadata["called_by"] == "answer_question"


@pytest.mark.asyncio
async def test_code_graph_investigator_uses_reason_when_queries_are_empty() -> None:
    provider = FakeCodeGraphProvider([])
    agent = CodeGraphInvestigatorAgent(provider)
    decision = make_decision([])

    await agent.run(CodeGraphInvestigatorInput(decision=decision))

    assert provider.queries is not None
    assert provider.queries[0] == "Find callers for rerank_documents."
