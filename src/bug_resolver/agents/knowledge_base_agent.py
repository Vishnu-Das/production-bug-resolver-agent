from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.knowledge.base import KnowledgeBaseProvider
from bug_resolver.rules.knowledge_base_rules import KnowledgeBaseRules
from bug_resolver.schemas import ContextPlan, KnowledgeContext
from bug_resolver.schemas.common import StrictBaseModel


class KnowledgeBaseInput(StrictBaseModel):
    context_plan: ContextPlan
    limit: int = Field(default=5, gt=0)


class KnowledgeBaseAgent(BaseAgent[KnowledgeBaseInput, list[KnowledgeContext]]):
    """
    Coordinates knowledge-base retrieval.

    The agent does not know whether docs come from local files, MCP,
    GitHub wiki, Notion, Confluence, or past RCA reports.

    It depends only on KnowledgeBaseProvider.
    """

    name = "knowledge_base_agent"

    def __init__(
        self,
        knowledge_base_provider: KnowledgeBaseProvider,
        rules: KnowledgeBaseRules | None = None,
    ) -> None:
        self._knowledge_base_provider = knowledge_base_provider
        self._rules = rules or KnowledgeBaseRules()

    async def _run(self, input_data: KnowledgeBaseInput) -> list[KnowledgeContext]:
        queries = self._rules.build_search_queries(input_data.context_plan)

        if not queries:
            return []

        contexts = await self._knowledge_base_provider.search_knowledge(
            queries=queries,
            limit=input_data.limit,
        )

        prioritized_contexts = self._rules.prioritize_contexts(
            contexts=contexts,
            context_plan=input_data.context_plan,
        )

        return self._rules.limit_contexts(
            contexts=prioritized_contexts,
            limit=input_data.limit,
        )