from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.code.base import CodeContextProvider
from bug_resolver.rules.code_context_rules import CodeContextRules
from bug_resolver.schemas import CodeContext, ContextPlan
from bug_resolver.schemas.common import StrictBaseModel


class CodeContextInput(StrictBaseModel):
    context_plan: ContextPlan
    limit: int = Field(default=5, gt=0)


class CodeContextAgent(BaseAgent[CodeContextInput, list[CodeContext]]):
    """
    Coordinates code context retrieval.

    The agent does not know FAISS, embeddings, or indexing details.
    It depends only on CodeContextProvider.
    """

    name = "code_context_agent"

    def __init__(
        self,
        code_context_provider: CodeContextProvider,
        rules: CodeContextRules | None = None,
    ) -> None:
        self._code_context_provider = code_context_provider
        self._rules = rules or CodeContextRules()

    async def _run(self, input_data: CodeContextInput) -> list[CodeContext]:
        queries = self._rules.build_search_queries(input_data.context_plan)

        if not queries:
            return []

        contexts = await self._code_context_provider.search_code(
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