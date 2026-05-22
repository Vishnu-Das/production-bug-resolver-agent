"""Code graph provider protocol for retrieving structural code evidence."""

from typing import Protocol, runtime_checkable

from bug_resolver.schemas import CodeGraphContext


@runtime_checkable
class CodeGraphProvider(Protocol):
    """Contract for retrieving AST-derived structural code context."""

    async def search_graph(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeGraphContext]:
        """Search structural code context using one or more focused queries."""
        ...
