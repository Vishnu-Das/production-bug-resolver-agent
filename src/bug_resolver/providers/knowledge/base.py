"""Knowledge-base provider protocol for retrieving documentation evidence."""

from typing import Protocol, runtime_checkable

from bug_resolver.schemas import KnowledgeContext


@runtime_checkable
class KnowledgeBaseProvider(Protocol):
    """Contract for retrieving documentation, README, runbook, and design context."""

    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        """Search knowledge base documents using one or more focused queries."""
        ...
