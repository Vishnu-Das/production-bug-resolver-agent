"""Parallel execution coordinator for planned context retrieval routes."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import dataclass

from bug_resolver.providers.retrieval import (
    CodeGraphExpansionProvider,
    ExactSearchProvider,
    FileContextProvider,
    KnowledgeSearchProvider,
    SemanticCodeSearchProvider,
    StructuralSearchProvider,
)
from bug_resolver.schemas import (
    EvidenceCandidate,
    RetrievalBatchResult,
    RetrievalPlan,
    RetrievalProviderFailure,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ProviderCall:
    route: str
    provider_name: str
    awaitable: Awaitable[list[EvidenceCandidate]]


class ParallelContextRetriever:
    """Run available planned retrieval routes concurrently and preserve partial results."""

    def __init__(
        self,
        *,
        file_context_provider: FileContextProvider | None = None,
        exact_search_provider: ExactSearchProvider | None = None,
        structural_search_provider: StructuralSearchProvider | None = None,
        semantic_code_search_provider: SemanticCodeSearchProvider | None = None,
        code_graph_provider: CodeGraphExpansionProvider | None = None,
        knowledge_search_provider: KnowledgeSearchProvider | None = None,
    ) -> None:
        self._file_context_provider = file_context_provider
        self._exact_search_provider = exact_search_provider
        self._structural_search_provider = structural_search_provider
        self._semantic_code_search_provider = semantic_code_search_provider
        self._code_graph_provider = code_graph_provider
        self._knowledge_search_provider = knowledge_search_provider

    async def retrieve(self, plan: RetrievalPlan) -> RetrievalBatchResult:
        """Execute populated routes in parallel without ranking or transforming candidates."""
        calls = self._build_calls(plan)
        if not calls:
            return RetrievalBatchResult()

        responses = await asyncio.gather(
            *(call.awaitable for call in calls),
            return_exceptions=True,
        )

        candidates: list[EvidenceCandidate] = []
        failures: list[RetrievalProviderFailure] = []
        warnings: list[str] = []
        for call, response in zip(calls, responses, strict=True):
            if isinstance(response, BaseException):
                if not isinstance(response, Exception):
                    raise response
                failure = self._build_failure(call, response)
                failures.append(failure)
                warning = (
                    f"{failure.route} retrieval failed in {failure.provider_name}: "
                    f"{failure.error_type}: {failure.message}"
                )
                warnings.append(warning)
                logger.warning(warning)
                continue
            candidates.extend(response)

        return RetrievalBatchResult(
            candidates=candidates,
            warnings=warnings,
            failed_retrievers=[failure.route for failure in failures],
            failures=failures,
        )

    def _build_calls(self, plan: RetrievalPlan) -> list[_ProviderCall]:
        calls: list[_ProviderCall] = []

        if self._file_context_provider is not None and plan.file_context_requests:
            calls.append(
                _ProviderCall(
                    route="file_context",
                    provider_name=self._provider_name(self._file_context_provider),
                    awaitable=self._file_context_provider.read_context(plan.file_context_requests),
                )
            )
        if self._exact_search_provider is not None and plan.exact_queries:
            calls.append(
                _ProviderCall(
                    route="exact_search",
                    provider_name=self._provider_name(self._exact_search_provider),
                    awaitable=self._exact_search_provider.search_exact(plan.exact_queries),
                )
            )
        if self._structural_search_provider is not None and plan.structural_queries:
            calls.append(
                _ProviderCall(
                    route="structural_search",
                    provider_name=self._provider_name(self._structural_search_provider),
                    awaitable=self._structural_search_provider.search_structure(
                        plan.structural_queries
                    ),
                )
            )
        if self._semantic_code_search_provider is not None and plan.semantic_queries:
            calls.append(
                _ProviderCall(
                    route="semantic_code_search",
                    provider_name=self._provider_name(self._semantic_code_search_provider),
                    awaitable=self._semantic_code_search_provider.search_semantic_code(
                        plan.semantic_queries
                    ),
                )
            )
        if self._code_graph_provider is not None and plan.graph_expansion_requests:
            calls.append(
                _ProviderCall(
                    route="code_graph_expansion",
                    provider_name=self._provider_name(self._code_graph_provider),
                    awaitable=self._code_graph_provider.expand_context(
                        plan.graph_expansion_requests
                    ),
                )
            )
        if self._knowledge_search_provider is not None and plan.kb_queries:
            calls.append(
                _ProviderCall(
                    route="knowledge_search",
                    provider_name=self._provider_name(self._knowledge_search_provider),
                    awaitable=self._knowledge_search_provider.search_knowledge(plan.kb_queries),
                )
            )

        return calls

    def _provider_name(self, provider: object) -> str:
        return type(provider).__name__

    def _build_failure(
        self,
        call: _ProviderCall,
        error: Exception,
    ) -> RetrievalProviderFailure:
        return RetrievalProviderFailure(
            route=call.route,
            provider_name=call.provider_name,
            error_type=type(error).__name__,
            message=str(error) or type(error).__name__,
        )
